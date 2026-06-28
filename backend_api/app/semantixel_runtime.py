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
    "audio": {
        "enabled": True,
        "transcription_enabled": True,
        "clap_enabled": False,
        "max_duration_seconds": 0,
        "provider": "faster_whisper",
        "faster_whisper_model": "tiny.en",
        "transcription_max_duration": 60.0,
    },
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
        self._scan_completed = False
        self._scan_lock = RLock()
        self._scan_in_progress = False

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", False))

    def initialize(self) -> None:
        """Load Semantixel services lazily inside this backend process."""
        if not self.enabled:
            return

        from semantixel.services.index_service import IndexService
        from semantixel.services.model_manager import model_manager
        from semantixel.services.search_service import SearchService

        db_path = str(self.settings.get("db_path", _DEFAULT_MULTIMODAL_CONFIG["db_path"]))

        # Keep model loading lazy: wiring model_manager here does not load models until
        # IndexService/SearchService operations access model_manager providers.
        _ = model_manager

        self.index_service = IndexService(db_path=db_path)
        self.search_service = SearchService(self.index_service, _NoopFaceService())
        self._apply_scan_scope()

    def _ensure_search_index_ready(self) -> None:
        """Build the multimodal index on first search when the store is empty."""
        if self.index_service is None:
            raise RuntimeError("Semantixel index service is not initialized")

        include_dirs, _exclude_dirs = self._apply_scan_scope()
        if not include_dirs:
            return

        if self._scan_completed:
            return

        with self._scan_lock:
            if self._scan_completed:
                return
            if self._scan_in_progress:
                logger.info("Scan already in progress by another request, waiting...")
                return

            self._scan_in_progress = True

        indexed_count = 0
        for col_name in ("image_collection", "text_collection", "audio_collection"):
            try:
                indexed_count += int(getattr(self.index_service, col_name).count())
            except StopIteration:
                pass
            except Exception as exc:
                logger.warning("Unable to count %s: %s", col_name, exc)

        if indexed_count > 0:
            with self._scan_lock:
                self._scan_completed = True
                self._scan_in_progress = False
            return

        logger.info("Multimodal index is empty or needs refresh. Running scan before search.")
        try:
            self.index_service.run_full_scan()
        finally:
            with self._scan_lock:
                self._scan_completed = True
                self._scan_in_progress = False

    def _apply_scan_scope(self) -> tuple[list[str], list[str]]:
        """Apply include/exclude directories to Semantixel global config.

        include_directories defines scan roots; exclude_directories prunes subtrees
        from those roots. Excludes outside include roots are ignored.
        """
        from semantixel.core.config import config as sem_config

        include_raw = self.settings.get("include_directories", [])
        exclude_raw = self.settings.get("exclude_directories", [])

        include_dirs: list[str] = []
        for candidate in include_raw if isinstance(include_raw, list) else []:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            resolved = Path(candidate).expanduser().resolve()
            if resolved.exists() and resolved.is_dir():
                include_dirs.append(str(resolved))

        exclude_dirs: list[str] = []
        for candidate in exclude_raw if isinstance(exclude_raw, list) else []:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            resolved = Path(candidate).expanduser().resolve()
            if not resolved.exists() or not resolved.is_dir():
                continue

            resolved_str = str(resolved)
            under_include = False
            for inc in include_dirs:
                try:
                    if Path(resolved_str).is_relative_to(Path(inc)):
                        under_include = True
                        break
                except ValueError:
                    continue

            if under_include:
                exclude_dirs.append(resolved_str)

        sem_config.include_directories = include_dirs
        sem_config.exclude_directories = exclude_dirs
        audio_settings = self.settings.get("audio")
        if isinstance(audio_settings, dict):
            for key, value in audio_settings.items():
                if hasattr(sem_config.audio, key):
                    setattr(sem_config.audio, key, value)
        return include_dirs, exclude_dirs

    def run_full_scan(self) -> dict[str, Any]:
        """Run multimodal indexing via Semantixel IndexService orchestrator.

        IndexService internally reuses semantixel.utils.scan_utils for media discovery
        and semantixel.utils.video_utils for video frame extraction.
        """
        if self.index_service is None:
            raise RuntimeError("Semantixel index service is not initialized")

        include_dirs, exclude_dirs = self._apply_scan_scope()
        if not include_dirs:
            return {
                "status": "noop",
                "message": "Multimodal indexing skipped: include_directories is empty or contains no existing directories.",
                "source": "semantixel",
                "scan_roots": [],
                "excluded_roots": exclude_dirs,
            }

        self.index_service.run_full_scan()
        return {
            "status": "ok",
            "message": "Multimodal indexing completed",
            "source": "semantixel",
            "scan_roots": include_dirs,
            "excluded_roots": exclude_dirs,
        }

    def semantic_text_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        media_type: str = "all",
    ) -> list[dict[str, Any]]:
        """Search images/video frames with CLIP text embeddings."""
        if self.search_service is None:
            raise RuntimeError("Semantixel runtime is not initialized")

        self._ensure_search_index_ready()

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

    def semantic_image_search(
        self,
        image_path: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        media_type: str = "all",
    ) -> list[dict[str, Any]]:
        """Search visually similar images/video frames from a reference image."""
        if self.search_service is None:
            raise RuntimeError("Semantixel runtime is not initialized")

        self._ensure_search_index_ready()

        resolved_top_k = int(top_k if top_k is not None else self.settings.get("top_k_default", 5))
        resolved_threshold = float(
            threshold if threshold is not None else self.settings.get("threshold_default", 0.0)
        )

        return self.search_service.semantic_image_search(
            image_path=image_path,
            top_k=max(1, resolved_top_k),
            threshold=resolved_threshold,
            media_type=media_type,
        )

    def keyword_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        media_type: str = "all",
    ) -> list[dict[str, Any]]:
        """Search OCR text and audio transcripts using BM25 keywords."""
        if self.search_service is None:
            raise RuntimeError("Semantixel runtime is not initialized")

        self._ensure_search_index_ready()

        resolved_top_k = int(top_k if top_k is not None else self.settings.get("top_k_default", 5))
        resolved_threshold = float(threshold if threshold is not None else 0.0)
        return self.search_service.keyword_search(
            query=query,
            top_k=max(1, resolved_top_k),
            threshold=resolved_threshold,
            media_type=media_type,
        )

    def graph_data(self) -> dict[str, Any]:
        """Return the CLIP similarity graph for indexed visual media."""
        if self.search_service is None:
            raise RuntimeError("Semantixel runtime is not initialized")

        self._ensure_search_index_ready()
        return self.search_service.generate_graph_data()


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
    if isinstance(mm.get("audio"), dict):
        audio_settings = dict(settings["audio"])
        audio_settings.update(mm["audio"])
        settings["audio"] = audio_settings

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
        # Support runtime config toggles without requiring full process restart.
        rebuild_semantixel_runtime(raise_on_error=False)
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
    runtime_loaded = runtime is not None

    if not enabled:
        multimodal_store_status = "disabled"
    elif runtime_loaded and getattr(runtime, "index_service", None) is not None:
        multimodal_store_status = "ready"
    elif runtime_error:
        multimodal_store_status = "error"
    else:
        multimodal_store_status = "unavailable"

    return {
        "enabled": enabled,
        "ready": ready,
        "runtime_loaded": runtime_loaded,
        "multimodal_store_status": multimodal_store_status,
        "runtime_error": runtime_error,
        "db_path": settings.get("db_path"),
        "include_directories": settings.get("include_directories", []),
        "exclude_directories": settings.get("exclude_directories", []),
        "top_k_default": settings.get("top_k_default", 5),
        "threshold_default": settings.get("threshold_default", 0.0),
        "audio": settings.get("audio", {}),
    }


def shutdown_semantixel_runtime() -> None:
    """Release Semantixel runtime resources for clean backend shutdown."""
    with _lock:
        runtime = _state.get("runtime")

        if runtime is not None:
            try:
                from semantixel.services.model_manager import model_manager

                model_manager.unload_all()
            except (ImportError, RuntimeError, OSError, ValueError):
                logger.exception("Failed while unloading Semantixel models")

            # Drop references to allow GC and GPU memory release.
            runtime.search_service = None
            runtime.index_service = None

        _state["runtime"] = None
        _state["runtime_error"] = None
        logger.info("Semantixel runtime shut down")


rebuild_semantixel_runtime(raise_on_error=False)
