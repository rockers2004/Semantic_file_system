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
from typing import Optional
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, Field

from backend_api.app.logging_config import configure_logging

configure_logging()

from backend_api.app.backend_facade import get_backend_facade

app = FastAPI(title="Semantic File System API", version="0.1.0")
backend_facade = get_backend_facade()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Safe for local desktop app (not a web service)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def initialize_runtime_layers() -> None:
    """Initialize all backend-managed runtimes in this same process."""
    backend_facade.initialize()


@app.on_event("shutdown")
async def shutdown_runtime_layers() -> None:
    """Shut down all backend-managed runtimes in this same process."""
    backend_facade.shutdown()

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
    mode: str = "general"
    media_type: str = "all"
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Query cannot be empty")
        return value.strip()

    @field_validator("media_type")
    @classmethod
    def validate_media_type(cls, value: str) -> str:
        normalized = (value or "all").strip().lower()
        if normalized not in {"all", "image", "video"}:
            raise ValueError("media_type must be one of: all, image, video")
        return normalized


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


class IndexingRequest(BaseModel):
    target: str = "text"

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"text", "multimodal", "all"}:
            raise ValueError("target must be one of: text, multimodal, all")
        return normalized

class ConfigUpdateRequest(BaseModel):
    root_path: str


MAX_TEXT_PREVIEW_BYTES = 1_000_000




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
    backend_snapshot = backend_facade.health_snapshot()
    slpfs_snapshot = backend_snapshot.get("slpfs", {})
    semantixel_snapshot = backend_snapshot.get("semantixel", {})

    backend_ok = slpfs_snapshot.get("backend") == "ready"
    ollama_ok = slpfs_snapshot.get("ollama_status") == "ready"
    sem_enabled = bool(semantixel_snapshot.get("enabled"))
    sem_ready = bool(semantixel_snapshot.get("ready"))

    health_status = backend_snapshot.get("status", "degraded")
    slpfs_runtime_error = slpfs_snapshot.get("runtime_error")
    multimodal_runtime_error = semantixel_snapshot.get("runtime_error")

    return SuccessResponse(
        ok=True,
        data={
            # Aggregated UI-friendly status
            "health_status": health_status,
            # Backward-compatible alias
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),

            # Required explicit runtime/loading status fields
            "slpfs_runtime_loaded": slpfs_snapshot.get("runtime_loaded", False),
            "multimodal_runtime_loaded": semantixel_snapshot.get("runtime_loaded", False),
            "ollama_status": slpfs_snapshot.get("ollama_status", "unavailable"),
            "vector_store_status": slpfs_snapshot.get("vector_store_status", "error"),
            "multimodal_store_status": semantixel_snapshot.get("multimodal_store_status", "unavailable"),
            "current_root": slpfs_snapshot.get("root_path"),
            "multimodal_db_path": semantixel_snapshot.get("db_path"),
            "slpfs_runtime_error": slpfs_runtime_error,
            "multimodal_runtime_error": multimodal_runtime_error,
            "runtime_errors": {
                "slpfs": slpfs_runtime_error,
                "multimodal": multimodal_runtime_error,
            },

            # Per-subsystem details for diagnostics
            "subsystems": {
                "slpfs": slpfs_snapshot,
                "multimodal": semantixel_snapshot,
            },

            # Legacy fields retained for compatibility
            "backend_status": "ok" if backend_ok else ("error" if slpfs_snapshot.get("runtime_error") else "unknown"),
            "runtime_loaded": slpfs_snapshot.get("runtime_loaded", False),
            "ollama_status_legacy": "ok" if ollama_ok else "unavailable",
            "model_status": "ok" if (ollama_ok and slpfs_snapshot.get("model_status") == "ready") else "not_available",
            "indexed_file_count": slpfs_snapshot.get("indexed_files", 0),
            "runtime_error": slpfs_runtime_error,
            "ollama_model": slpfs_snapshot.get("ollama_model"),
            "embedding_model": slpfs_snapshot.get("embedding_model"),
            "multimodal_enabled": sem_enabled,
            "multimodal_ready": sem_ready,
            "multimodal_error": multimodal_runtime_error,
        },
        meta=Meta(request_id=request.state.request_id),
    )


# Config Endpoint
@app.get("/api/v1/config")
async def get_config(request: Request):
    """Get current configuration"""
    return SuccessResponse(
        ok=True,
        data=backend_facade.config_snapshot(),
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
        updated_root = backend_facade.update_root_path(payload.root_path)
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
    try:
        data = backend_facade.list_tree(path=path, depth=depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SuccessResponse(
        ok=True,
        data=data,
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
    payload = ErrorResponse(
        ok=False,
        error=ErrorPayload(
            code="HTTP_ERROR",
            message=str(exc.detail),
            details={"status_code": exc.status_code},
        ),
        meta=Meta(request_id=request.state.request_id),
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.post("/api/v1/file/read")
async def read_file(request: Request, payload: FileReadRequest):
    """
    Read a file within the configured root and return its text content.
    """
    try:
        data = backend_facade.read_text_file(payload.path, MAX_TEXT_PREVIEW_BYTES)
    except ValueError as exc:
        detail = str(exc)
        status = 415 if "preview" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IsADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to read file") from exc

    return SuccessResponse(
        ok=True,
        data=data,
        meta=Meta(request_id=request.state.request_id),
    )

@app.post("/api/v1/search")
async def search_files(request: Request, payload: SearchRequest):
    """
    Search via SLPFS runtime and map results to frontend contract.
    Optional fallback can be enabled explicitly when runtime is unavailable.
    """
    try:
        data = backend_facade.search_text(
            query=payload.query.strip(),
            k=payload.k,
            mode=payload.mode,
            top_k=payload.top_k,
            threshold=payload.threshold,
            media_type=payload.media_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "semantixel runtime is disabled" in str(exc).lower():
            return SuccessResponse(
                ok=True,
                data={
                    "query": payload.query.strip(),
                    "total": 0,
                    "results": [],
                    "source": "semantixel",
                    "search_status": "failed",
                    "error": "Multimodal search is disabled in config. Switch mode to General or enable multimodal.",
                },
                meta=Meta(request_id=request.state.request_id),
            )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Search failed") from exc

    return SuccessResponse(
        ok=True,
        data=data,
        meta=Meta(request_id=request.state.request_id),
    )


@app.post("/api/v1/command")
async def run_command(request: Request, payload: CommandRequest):
    """
    Excute natural language commands through SLPFS runtime and return
    a normalized API envelop for success/failure outcomes.
    """
    try:
        text = payload.text.strip()
        result = backend_facade.run_command(text)
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

    raw_results = result.get("results", [])
    command_results = []
    if isinstance(raw_results, list):
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            path = (
                item.get("path")
                or item.get("file_path")
                or item.get("relative_path")
                or ""
            )
            file_name = item.get("file_name") or ""
            preview = item.get("snippet") or item.get("preview") or ""
            if not preview:
                preview = f"{file_name} | {path}".strip(" |")
            command_results.append(
                {
                    "path": path,
                    "score": float(item.get("score", 0.0) or 0.0),
                    "snippet": preview,
                    "is_dir": False,
                }
            )

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
            "results": command_results,
            "slpfs_success": success,
            "slpfs_error": error_message or None,
            "ollama_output": result.get("ollama_output"),
            "stats": result.get("stats") if isinstance(result.get("stats"), dict) else None,
            "skipped_files": (
                result.get("stats", {}).get("skipped_files", [])
                if isinstance(result.get("stats"), dict)
                else []
            ),
        },
        meta=Meta(request_id=request.state.request_id),
    )


@app.post("/api/v1/index")
async def trigger_indexing(request: Request, payload: IndexingRequest):
    """Trigger indexing for text, multimodal, or both runtimes."""
    try:
        data = backend_facade.trigger_indexing(payload.target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Indexing failed") from exc

    return SuccessResponse(
        ok=True,
        data=data,
        meta=Meta(request_id=request.state.request_id),
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
