"""
FastAPI backend for Semantic File System
Bridges Tauri frontend with Python core modules
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime
from pathlib import Path
import os

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


ROOT_PATH = Path(os.getenv("SLPFS_ROOT", str(Path.cwd()))).resolve()


def _resolve_safe_path(raw_path: Optional[str]) -> Path:
    """Resolve a path and ensure it stays within the configured root."""
    candidate = ROOT_PATH if not raw_path else Path(raw_path).resolve()
    try:
        candidate.relative_to(ROOT_PATH)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path is outside allowed root") from exc
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
            "ollama": "checking...",  # TODO: implement Ollama health check
            "model": "checking...",   # TODO: implement model check
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
            "root_path": str(ROOT_PATH),
            "max_depth": 10,
        },
        meta=Meta(request_id=request.state.request_id),
    )


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
            "root": str(ROOT_PATH),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
