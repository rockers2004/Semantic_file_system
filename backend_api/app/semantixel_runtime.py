"""Semantixel multimodal runtime bootstrap for backend API modules.

This module owns at most one Semantixel service instance for the backend process.
It is intentionally defensive: initialization failures are captured in state so the
main backend remains available even if multimodal dependencies are incomplete.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any, Optional

import yaml

import logging

logger = logging.getLogger(__name__)


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

_DEFAULT_MULTIMODAL_CONFIG: dict[str, Any] = {
    "enabled": False,
    "db_path": "./db_multimodal",
    "include_directories": [],
    "exclude_directories": [],
    "top_k_default": 5,
    "threshold_default": 0.0,
}


class _NoopFaceService:
    """Fallback face service used when DeepFace is unavailable."""

    def search_by_name(self, name_query: str, threshold: float = 0.6) -> list[str]:
        _ = (name_query, threshold)
        return []


class SemantixelRuntimeService:
    """In-process runtime wrapper for Semantixel services."""

    def __init__(self, settings: dict[str, Any]):
        self.settings = settings
        self.index_service = None
        self.search_service = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", False))

    def initialize(self) -> None:
        """Load Semantixel services lazily inside this backend process."""
        if not self.enabled:
            return

        from semantixel.core.config import config as sem_config
        from semantixel.services.index_service import IndexService
        from semantixel.services.search_service import SearchService

        include_dirs = list(self.settings.get("include_directories", []))
        exclude_dirs = list(self.settings.get("exclude_directories", []))

        # Semantixel services read these globals today; set them from multimodal config.
        sem_config.include_directories = include_dirs
        sem_config.exclude_directories = exclude_dirs

        db_path = str(self.settings.get("db_path", _DEFAULT_MULTIMODAL_CONFIG["db_path"]))

        self.index_service = IndexService(db_path=db_path)
        self.search_service = SearchService(self.index_service, _NoopFaceService())

    def semantic_text_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        media_type: str = "image",
    ) -> list[dict[str, Any]]:
        """Search images/video frames with CLIP text embeddings."""
        if self.search_service is None:
            raise RuntimeError("Semantixel runtime is not initialized")

        resolved_top_k = int(top_k if top_k is not None else self.settings.get("top_k_default", 5))
        resolved_threshold = float(
            threshold if threshold is not None else self.settings.get("threshold_default", 0.0)
        )

        return self.search_service.semantic_text_search(
            query=query,
            top_k=max(1, resolved_top_k),
            threshold=resolved_threshold,
            media_type=media_type,
        )


_lock = RLock()
_state: dict[str, Any] = {
    "runtime": None,
    "runtime_error": None,
    "settings": dict(_DEFAULT_MULTIMODAL_CONFIG),
}


def _load_multimodal_config() -> dict[str, Any]:
    """Load multimodal config section from config.yaml with safe defaults."""
    settings = dict(_DEFAULT_MULTIMODAL_CONFIG)

    if not CONFIG_PATH.exists():
        return settings

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}

    if not isinstance(loaded, dict):
        return settings

    mm = loaded.get("multimodal")
    if not isinstance(mm, dict):
        return settings

    settings["enabled"] = bool(mm.get("enabled", settings["enabled"]))
    settings["db_path"] = str(mm.get("db_path", settings["db_path"]))
    settings["include_directories"] = list(mm.get("include_directories", settings["include_directories"]))
    settings["exclude_directories"] = list(mm.get("exclude_directories", settings["exclude_directories"]))
    settings["top_k_default"] = int(mm.get("top_k_default", settings["top_k_default"]))
    settings["threshold_default"] = float(mm.get("threshold_default", settings["threshold_default"]))

    return settings


def rebuild_semantixel_runtime(*, raise_on_error: bool = False) -> None:
    """Rebuild Semantixel runtime from current multimodal config."""
    with _lock:
        settings = _load_multimodal_config()
        _state["settings"] = settings

        if not settings.get("enabled", False):
            _state["runtime"] = None
            _state["runtime_error"] = None
            logger.info("Semantixel runtime is disabled by config")
            return

        try:
            runtime = SemantixelRuntimeService(settings)
            runtime.initialize()
            _state["runtime"] = runtime
            _state["runtime_error"] = None
            logger.info("Semantixel runtime initialized")
        except (ImportError, OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
            _state["runtime"] = None
            _state["runtime_error"] = str(exc)
            logger.exception("Failed to initialize Semantixel runtime")
            if raise_on_error:
                raise RuntimeError(f"Failed to initialize Semantixel runtime: {exc}") from exc


def get_semantixel_runtime() -> SemantixelRuntimeService:
    """Return Semantixel runtime when enabled and available."""
    with _lock:
        settings = _state["settings"]
        runtime = _state["runtime"]
        runtime_error = _state["runtime_error"]

        if not settings.get("enabled", False):
            raise RuntimeError("Semantixel runtime is disabled")

        if runtime is None:
            if runtime_error:
                raise RuntimeError(f"Semantixel runtime not available: {runtime_error}")
            raise RuntimeError("Semantixel runtime not initialized")

        return runtime


def get_semantixel_config() -> dict[str, Any]:
    """Return loaded multimodal config values."""
    with _lock:
        return dict(_state["settings"])


def get_semantixel_health_snapshot() -> dict[str, Any]:
    """Return Semantixel runtime health snapshot for API status endpoints."""
    with _lock:
        settings = dict(_state["settings"])
        runtime = _state["runtime"]
        runtime_error = _state["runtime_error"]

    enabled = bool(settings.get("enabled", False))
    ready = enabled and runtime is not None and not runtime_error

    return {
        "enabled": enabled,
        "ready": ready,
        "runtime_error": runtime_error,
        "db_path": settings.get("db_path"),
        "include_directories": settings.get("include_directories", []),
        "exclude_directories": settings.get("exclude_directories", []),
        "top_k_default": settings.get("top_k_default", 5),
        "threshold_default": settings.get("threshold_default", 0.0),
    }


rebuild_semantixel_runtime(raise_on_error=False)
