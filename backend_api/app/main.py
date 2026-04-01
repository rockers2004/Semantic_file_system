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
    - Handle search requests (MVP placeholder implementation)
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
    - Search endpoint currently contains placeholder logic
    - Designed for local desktop usage (Tauri integration)
    - CORS is enabled for development flexibility
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List
import uuid
from datetime import datetime
from pathlib import Path
import os
import yaml

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

class SearchResultItem(BaseModel):
    path: str
    score: float
    preview: Optional[str] = None


class SearchResponse(BaseModel):
    query:str
    k: int
    mode: str
    results: List[SearchResultItem]


class FileReadRequest(BaseModel):
    path: str

class ConfigUpdateRequest(BaseModel):
    root_path: str

CONFIG_FILE = Path(__file__).resolve().parents[2] / "config.yaml"


def _load_root_from_config() -> Optional[Path]:
    """
    Loads the root directory from config.yaml if it exists and is valid.
    
    Returns:
        Optional[Path]: Valid root path or None if invalid/missing
    """
    if not CONFIG_FILE.exists():
        return None

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            config_data = yaml.safe_load(file) or {}
    except (OSError, yaml.YAMLError):
        return None

    raw_root = str(config_data.get("directories", {}).get("root_dir", "")).strip()
    if not raw_root:
        return None

    try:
        path = Path(raw_root).expanduser().resolve()
    except OSError:
        return None

    if not path.exists() or not path.is_dir():
        return None

    return path


def _save_root_to_config(root_path: Path) -> None:
    """
    persists the current root direcotory into config.yaml
    Updats only the root field without affecting other config.
    
    Args:
        root_path (Path): The root directory path to save
    Raises:
        OSError: If there is an issue writing to the config file
    returns:
        None
    """
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            config_data = yaml.safe_load(file) or {}
    except (OSError, yaml.YAMLError):
        config_data = {}

    directories = config_data.get("directories")
    if not isinstance(directories, dict):
        directories = {}
    directories["root_dir"] = str(root_path)
    config_data["directories"] = directories

    with CONFIG_FILE.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config_data, file, sort_keys=False)


_env_root = os.getenv("SLPFS_ROOT")
if _env_root:
    _current_root = Path(_env_root).expanduser().resolve()
else:
    _current_root = _load_root_from_config() or Path.cwd().resolve()

_state = {"root_path": _current_root}

try:
    _save_root_to_config(_current_root)
except OSError:
    # App can still run with in-memory root even if persistence write fails at startup.
    pass




def get_root() -> Path:
    """
    Retrieves the current root directory path from the application state.
    
    Returns:
        Path: The current root directory path.
    """
    return _state["root_path"]



def set_root(new_root: Path):
    """
    Updates the current root directory at runtime and persists it
    to config.yaml. Also updates the in-memory state for immediate effect.
    
    Args:
        new_root (Path): The new root directory path to set.
    Raises:
        HTTPException: If there is an issue persisting the new root to config.yaml.
    Returns:
        None
    """
    try:
        _save_root_to_config(new_root)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to persist root path to config.yaml") from exc
    _state["root_path"] = new_root


def validate_root_path(path_str: str) -> Path:
    """
    Validates a user-provided root path string, ensuring it is non-empty, exists, and is a directory.

    Args:
        path_str (str): The root path string to validate.
    Returns:
        Path: The validated root directory path.
    Raises:
        HTTPException: If the path is empty, does not exist, or is not a directory.
    """
    if not path_str or not path_str.strip():
        raise HTTPException(status_code=400, detail="Root path cannot be empty")
    
    path = Path(path_str).expanduser().resolve()

    if not path.exists():
        raise HTTPException(status_code=400, detail="Root path does not exist")

    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Root path must be a directory")
    return path


def _resolve_safe_path(raw_path: Optional[str]) -> Path:
    """
    Resolves a given path relative to the current root and ensures it does not escape the allowed directory.

    Args:
        raw_path (Optional[str]): The raw path string to resolve. If None or empty,
    Returns:
        Path: The resolved and validated path.
    """
    current_root = get_root()

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
    return SuccessResponse(
        ok=True,
        data={
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "backend": "ready",
            "ollama": "checking...",
            "model": "checking...",
        },
        meta=Meta(request_id=request.state.request_id),
    )


# Config Endpoint (placeholder)
@app.get("/api/v1/config")
async def get_config(request: Request):
    """Get current configuration"""
    return SuccessResponse(
        ok=True,
        data={
            "root_path": str(get_root()),
            "max_depth": 10,
        },
        meta=Meta(request_id=request.state.request_id),
    )

def _update_root_config_response(request: Request, payload: ConfigUpdateRequest) -> SuccessResponse:
    """
    Validates and updates root configuration, then builds a stadardized API response with updated values.

    Args:
        request (Request): FastAPI request object
        payload (ConfigUpdateRequest): Incoming config data
    Returns:
        SuccessResponse: Standardized API response with updated config data
    """
    new_root = validate_root_path(payload.root_path)
    set_root(new_root)
    return SuccessResponse(
        ok=True,
        data={
            "root_path": str(get_root()),
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
            "root": str(get_root()),
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
    Search for files matching the query within the configured root directory.
    This is a placeholder implementation that returns dummy results.
    In a real implementation, this would interface with the Ollama-based search module.
    """
    # search logic goes here
    return SuccessResponse(
        ok = True,
        data ={
            "query": payload.query,
            "k": payload.k,
            "mode": payload.mode,
            "results": []
        },
        meta = Meta(request_id=request.state.request_id)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
