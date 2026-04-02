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
    """Return a lightweight runtime health snapshot for API status endpoints."""
    with _lock:
        runtime = _state["runtime"]
        snapshot = {
            "runtime_ready": runtime is not None,
            "runtime_error": _state["runtime_error"],
            "config_path": str(CONFIG_PATH),
            "root_path": str(runtime.root_dir) if runtime else None,
            "ollama_model": runtime.config.ollama_model if runtime else None,
            "embedding_model": runtime.config.embedding_model if runtime else None,
        }
        logger.info("Generating SLPFS runtime health snapshot", extra=snapshot)
        return snapshot


def get_runtime_error() -> Optional[str]:
    """Return runtime initialization/rebuild error, if any."""
    with _lock:
        return _state["runtime_error"]


_initialize_runtime()
