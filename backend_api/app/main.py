"""
backend_api/main.py

Description:
    FastAPI-based backend service that powers the Semantic
    File System application. It acts as a bridge between the
    Tauri frontend and underlying file system operations.

Core Responsibilities:
    - Manage dynamic root directory configuration (with YAML persistence)
    - Ensure safe file access within the configured root
    - Provide file tree exploration and file content retrieval APIs
    - Handle semantic search and command requests via shared runtime
    - Standardize API responses with metadata and error handling

Key Features:
    - Runtime-updatable root path with persistence (config.yaml)
    - Secure path resolution to prevent directory traversal
    - Structured request/response models using Pydantic
    - Modular endpoint design for scalability
    - Request tracing using unique request IDs

Tech Stack:
    - FastAPI (API framework)
    - Pydantic (data validation)
    - PyYAML (configuration persistence)
    - Pathlib (filesystem handling)

Notes:
    - Designed for local desktop usage (Tauri integration)
    - CORS is enabled for development flexibility
"""
import os
from typing import Optional
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, Field

from backend_api.app.slpfs_runtime import (
    get_runtime,
    get_root_path,
    set_root_path,
    get_runtime_health_snapshot,
)

app = FastAPI(title="Semantic File System API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Safe for local desktop app (not a web service)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Response Models
class Meta(BaseModel):
    request_id: str


class SuccessResponse(BaseModel):
    ok: bool = True
    data: Optional[dict] = None
    error: Optional[dict] = None
    meta: Meta


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    ok: bool = False
    data: Optional[dict] = None
    error: Optional[ErrorPayload] = None
    meta: Meta

class SearchRequest(BaseModel):
    query: str
    k: int = Field(default=10, ge=1, le=50)
    mode: str = "normal"

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Query cannot be empty")
        return value.strip()


class CommandRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Text cannot be empty")
        return value.strip()


class FileReadRequest(BaseModel):
    path: str

class ConfigUpdateRequest(BaseModel):
    root_path: str



def _fallback_search_runtime_backup(query: str, k: int) -> list[dict]:
    """
    A simple fallback search implementation that performs a basic filename and content search
    within the configured root directory. This is used when the main SLPFS runtime search is unavailable.

    Args:
        query (str): The search query string.
        k (int): The maximum number of results to return.
    Returns:
        list[dict]: A list of search result dictionaries with file path, score, and preview.
    """
    root_dir = Path(get_root_path()).resolve()
    query_lower = query.lower()
    out: list[dict] = []

    for file_path in root_dir.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            name_match = query_lower in file_path.name.lower()
            content = file_path.read_text(encoding="utf-8", errors="replace")
            content_lower = content.lower()
            content_match = query_lower in content_lower
        except OSError:
            continue

        if not name_match and not content_match:
            continue

        score = 1.0 if name_match else 0.5
        snippet = ""
        if content_match:
            idx = content_lower.find(query_lower)
            start = max(0, idx - 80)
            end =min (len(content), idx + len(query) + 80)
            snippet = content[start:end].replace("\n", " ").replace("\r", " ")

        out.append(
            {
                "path": str(file_path),
                "score": score,
                "snippet": snippet,
                "is_dir": False,
            }
        )
        if len(out) >= k:
            break

    return out




def _resolve_safe_path(raw_path: Optional[str]) -> Path:
    """
    Resolves a given path relative to the current root and ensures it does not escape the allowed directory.

    Args:
        raw_path (Optional[str]): The raw path string to resolve. If None or empty,
    Returns:
        Path: The resolved and validated path.
    """
    current_root = Path(get_root_path()).resolve()

    if not raw_path:
        candidate = current_root
    else:
        requested_path = Path(raw_path)
        candidate = requested_path if requested_path.is_absolute() else current_root / requested_path
        candidate = candidate.resolve()

    try:
        candidate.relative_to(current_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path is outside of the configured root") from exc
    return candidate




# Middleware to add request_id
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    return response


# Health Check Endpoint
@app.get("/api/v1/health")
async def health_check(request: Request):
    """
    Check backend health status
    Returns status of backend and dependencies (Ollama, models)
    """
    snapshot = get_runtime_health_snapshot()

    backend_ok = snapshot.get("runtime_ready", False) and not snapshot.get("runtime_error")
    ollama_ok = snapshot.get("ollama_running", False)

    return SuccessResponse(
        ok=True,
        data={
            "status": "healthy" if (backend_ok and ollama_ok) else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "backend_status": "ok" if backend_ok else ("error" if snapshot.get("runtime_error") else "unknown"),
            "runtime_loaded": snapshot.get("runtime_ready", False),
            "ollama_status": "ok" if ollama_ok else "unavailable",
            "model_status": "ok" if (ollama_ok and snapshot.get("ollama_model")) else "not_available",
            "indexed_file_count": snapshot.get("indexed_files", 0),
            "current_root": snapshot.get("root_path"),
            "runtime_error": snapshot.get("runtime_error"),
            "ollama_model": snapshot.get("ollama_model"),
            "embedding_model": snapshot.get("embedding_model"),
        },
        meta=Meta(request_id=request.state.request_id),
    )


# Config Endpoint
@app.get("/api/v1/config")
async def get_config(request: Request):
    """Get current configuration"""
    return SuccessResponse(
        ok=True,
        data={
            "root_path": get_root_path(),
            "max_depth": 10,
        },
        meta=Meta(request_id=request.state.request_id),
    )

def _update_root_config_response(request: Request, payload: ConfigUpdateRequest) -> SuccessResponse:
    """
    Validates and updates root configuration, then builds a standardized API response with updated values.

    Args:
        request (Request): FastAPI request object
        payload (ConfigUpdateRequest): Incoming config data
    Returns:
        SuccessResponse: Standardized API response with updated config data
    """
    try:
        # Single validation + persistence + runtime rebuild in one call
        updated_root = set_root_path(payload.root_path)
    except ValueError as exc:
        # Validation errors from set_root_path
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Runtime rebuild errors
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SuccessResponse(
        ok=True,
        data={
            "root_path": updated_root,
            "max_depth": 10,
        },
        meta=Meta(request_id=request.state.request_id),
    )


@app.put("/api/v1/config")
async def update_config(request: Request, payload: ConfigUpdateRequest):
    """Update root path configuration."""
    return _update_root_config_response(request, payload)


@app.put("/api/v1/config/root")
async def update_config_root(request: Request, payload: ConfigUpdateRequest):
    """Backward-compatible root update endpoint."""
    return _update_root_config_response(request, payload)

@app.get("/api/v1/tree")
async def get_tree(request: Request, path: Optional[str] = None, depth: int = 1):
    """
    List directory entries for file tree rendering.

    Query params:
    - path: directory path to list (defaults to root)
    - depth: currently accepted for compatibility, used as 1-level listing
    """
    target = _resolve_safe_path(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries = []
    for entry in target.iterdir():
        try:
            stat = entry.stat()
            entries.append(
                {
                    "name": entry.name,
                    "path": str(entry.resolve()),
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        except OSError:
            # Skip entries that cannot be accessed.
            continue

    entries.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))

    return SuccessResponse(
        ok=True,
        data={
            "root": get_root_path(),
            "path": str(target),
            "depth": max(1, depth),
            "entries": entries,
        },
        meta=Meta(request_id=request.state.request_id),
    )


# Root endpoint
@app.get("/")
async def root():
    """API information"""
    return {
        "name": "Semantic File System API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# Error handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc):
    return ErrorResponse(
        ok=False,
        error=ErrorPayload(
            code="HTTP_ERROR",
            message=exc.detail,
            details={"status_code": exc.status_code},
        ),
        meta=Meta(request_id=request.state.request_id),
    )


@app.post("/api/v1/file/read")
async def read_file(request: Request, payload: FileReadRequest):
    """
    Read a file within the configured root and return its text content.
    """
    if not payload.path.strip():
        raise HTTPException(status_code=400, detail="Path is required")

    target = _resolve_safe_path(payload.path)

    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is a directory, not a file")

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to read file") from exc

    stat = target.stat()

    return SuccessResponse(
        ok=True,
        data={
            "path": str(target),
            "content": content,
            "encoding": "utf-8",
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        },
        meta=Meta(request_id=request.state.request_id),
    )

@app.post("/api/v1/search")
async def search_files(request: Request, payload: SearchRequest):
    """
    Search via SLPFS runtime and map results to frontend contract.
    Optional fallback can be enabled explicitly when runtime is unavailable.
    """
    query = payload.query.strip()
    k = payload.k
    use_fallback = str(os.getenv("SLPFS_SEARCH_FALLBACK", "0")).lower() in {"1", "true", "yes"}

    try:
        runtime = get_runtime()
        core_result = runtime.search_files(query=query, k=k, keywords=None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if not use_fallback:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        # explicit backup mode only
        fallback_items = _fallback_search_runtime_backup(query=query, k=k)
        return SuccessResponse(
            ok=True,
            data={
                "query": query,
                "total": len(fallback_items),
                "results": fallback_items,
            },
            meta = Meta(request_id=request.state.request_id),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Search failed") from exc
    
    # pass through clear SLPFS failure if present
    if not core_result.get("success", False):
        return SuccessResponse(
            ok=True,
            data={
                "query": query,
                "total": 0,
                "results": [],
                "source": "runtime",
                "search_status": "failed",
                "error": core_result.get("error", "Search failed "),
            },
            meta=Meta(request_id=request.state.request_id),
        )

    results = core_result.get("results", [])

    return SuccessResponse(
        ok=True,
        data={
            "query": query,
            "total": len(results),
            "results": [
                {
                    "path": item.get("file_path", ""),
                    "score": item.get("score", 0.0),
                    "snippet": item.get("preview", "") or "",
                    "is_dir": False,
                }
                for item in results
            ],
            "source": "runtime",
            "search_status": "ok",
        },
        meta=Meta(request_id=request.state.request_id),
    )


@app.post("/api/v1/command")
async def run_command(request: Request, payload: CommandRequest):
    """
    Excute natural language commands through SLPFS runtime and return
    a normalized API envelop for success/failure outcomes.
    """
    text = payload.text.strip()

    try:
        runtime = get_runtime()
        result = runtime.process_natural_language(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Command execution failed") from exc
    
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail = "Invalid command response from runtime")
    
    success = bool(result.get("success"))
    error_message = str(result.get("error") or "")
    lowered_error = error_message.lower()

    if success:
        command_status = "success"
        reason = None
    else:
        command_status = "failed"
        if "could not understand command" in lowered_error:
            reason = "low confidence"
        elif "llm" in lowered_error or "ollama" in lowered_error or "request failed" in lowered_error:
            reason = "llm error"
        else:
            reason = "execution error"

    return SuccessResponse(
        ok=True,
        data={
            "kind": "command",
            "input": text,
            "intent": "command",
            "command_status": command_status,
            "reason": reason,
            "message": result.get("summary") or result.get("message") or error_message or "",
            "parsed": {
                "raw": text,
                "action": result.get("operation", ""),
                "args": result.get("parameters", {}),
            },
            "results": result.get("results", []),
            "slpfs_success": success,
            "slpfs_error": error_message or None,
        },
        meta=Meta(request_id=request.state.request_id),
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
