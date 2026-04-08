"""Shared SLPFS runtime for backend API modules.

This module owns exactly one LocalSLPFS instance for the backend process.
It is intentionally thin: configuration/load/rebuild helpers only.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any, Optional

import yaml

from slpfs.config_loader import load_config_from_yaml
from slpfs.file_system import LocalSLPFS

import logging

logger = logging.getLogger(__name__)


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

_lock = RLock()
_state: dict[str, Any] = {
    "runtime": None,
    "runtime_error": None,
}


def _load_config():
    """Load SLPFS config from config.yaml."""
    return load_config_from_yaml(str(CONFIG_PATH))


def _build_runtime() -> LocalSLPFS:
    """Create a fresh LocalSLPFS instance from current config."""
    config = _load_config()
    logger.info(
        "Building LocalSLPFS runtime",
        extra={
            "config_path": str(CONFIG_PATH),
            "root_dir": config.root_dir,
            "vector_db_dir": config.vector_db_dir,
            "ollama_model": config.ollama_model,
            "embedding_model": config.embedding_model,
        },
    )
    return LocalSLPFS(config)


def _set_runtime(runtime: Optional[LocalSLPFS], error: Optional[str]) -> None:
    _state["runtime"] = runtime
    _state["runtime_error"] = error

def _rebuild_runtime(*, raise_on_error: bool = True) -> None:
    """Rebuild the shared runtime from current config and capture errors."""
    try:
        _set_runtime(_build_runtime(), None)
        logger.info("SLPFS runtime ready")
    except (ConnectionError, OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
        _set_runtime(None, str(exc))
        logger.exception("Failed to initialize SLPFS runtime")
        if raise_on_error:
            raise RuntimeError(f"Failed to initialize SLPFS runtime: {exc}") from exc


def _initialize_runtime() -> None:
    """Initialize runtime once at module import time."""
    with _lock:
        _rebuild_runtime(raise_on_error=False)


def _write_root_path_to_config(new_root: Path) -> None:
    """Persist root path in config.yaml while preserving other keys."""
    logger.info("persisting new root path to config", extra={"root_path": str(new_root)})

    data: dict[str, Any]
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            loaded = yaml.safe_load(file) or {}
            data = loaded if isinstance(loaded, dict) else {}
    else:
        data = {}

    directories = data.get("directories")
    if not isinstance(directories, dict):
        directories = {}

    directories["root_dir"] = str(new_root)
    data["directories"] = directories

    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False)


def get_runtime() -> LocalSLPFS:
    """Return the shared LocalSLPFS runtime instance."""
    with _lock:
        runtime = _state["runtime"]
        runtime_error = _state["runtime_error"]
        if runtime is None:
            logger.warning("SLPFS runtime requested before initialization", extra={"runtime_error": runtime_error})
            if runtime_error:
                raise RuntimeError(f"SLPFS runtime not available: {runtime_error}")
            raise RuntimeError("SLPFS runtime not initialized")
        return runtime


def get_root_path() -> str:
    """Return current runtime root path."""
    runtime = get_runtime()
    return str(runtime.root_dir)


def set_root_path(new_root: str) -> str:
    """Persist new root path and rebuild the shared runtime."""
    if not new_root or not new_root.strip():
        raise ValueError("Root path cannot be empty")

    resolved_root = Path(new_root).expanduser().resolve()
    if not resolved_root.exists():
        raise ValueError("Root path does not exist")
    if not resolved_root.is_dir():
        raise ValueError("Root path must be a directory")

    with _lock:
        logger.info("Updating SLPFS root path", extra={"new_root": str(resolved_root)})
        _write_root_path_to_config(resolved_root)
        _rebuild_runtime(raise_on_error=True)

    return str(resolved_root)


def get_runtime_health_snapshot() -> dict[str, Any]:
    """Return a stable runtime health snapshot for API status endpoints."""
    with _lock:
        runtime = _state["runtime"]
        runtime_error = _state["runtime_error"]

        snapshot = {
            "backend": "degraded",
            "runtime_loaded": runtime is not None,
            "root_path": str(runtime.root_dir) if runtime else None,
            "ollama_status": "unavailable",
            "model_status": "unknown",
            "vector_store_status": "error",
            "indexed_files": 0,
            "reindex_required": True,
            "runtime_error": runtime_error,
        }

        if runtime is None:
            return snapshot

        total_files = None

        # Vector store status + indexed files
        try:
            stats = runtime.get_stats()
            indexed = int(stats.get("indexed_files", 0) or 0)
            snapshot["indexed_files"] = indexed
            snapshot["vector_store_status"] = "ready"

            total_files_raw = stats.get("total_files")
            if isinstance(total_files_raw, int):
                total_files = total_files_raw
        except Exception as exc:
            snapshot["vector_store_status"] = "error"
            if not snapshot["runtime_error"]:
                snapshot["runtime_error"] = f"Vector store stats failed: {exc}"

        # Ollama status
        try:
            ollama_ok = bool(runtime.llm._test_connection())
            snapshot["ollama_status"] = "ready" if ollama_ok else "unavailable"
        except Exception as exc:
            snapshot["ollama_status"] = "error"
            if not snapshot["runtime_error"]:
                snapshot["runtime_error"] = f"Ollama health check failed: {exc}"

        # Model status
        model_name = str(getattr(runtime.config, "ollama_model", "") or "").strip()
        if not model_name:
            snapshot["model_status"] = "missing"
        elif snapshot["ollama_status"] == "ready":
            snapshot["model_status"] = "ready"
        else:
            snapshot["model_status"] = "unknown"

        # Reindex requirement
        if snapshot["vector_store_status"] == "ready" and isinstance(total_files, int):
            snapshot["reindex_required"] = snapshot["indexed_files"] < total_files
        else:
            snapshot["reindex_required"] = True

        # Backend aggregate
        if (
            snapshot["runtime_loaded"]
            and snapshot["ollama_status"] == "ready"
            and snapshot["vector_store_status"] == "ready"
            and not snapshot["runtime_error"]
        ):
            snapshot["backend"] = "ready"
        else:
            snapshot["backend"] = "degraded"

        return snapshot


def get_runtime_error() -> Optional[str]:
    """Return runtime initialization/rebuild error, if any."""
    with _lock:
        return _state["runtime_error"]


_initialize_runtime()
