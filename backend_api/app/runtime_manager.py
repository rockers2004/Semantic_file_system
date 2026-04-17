"""Backend runtime manager.

Coordinates all in-process runtimes owned by this backend process:
- SLPFS runtime bootstrap (slpfs_runtime.py)
- Semantixel multimodal runtime bootstrap (semantixel_runtime.py)

Also owns backend-level config persistence helpers so runtime modules do not
perform ad-hoc writes to config.yaml.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any, Callable

import yaml


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


_lock = RLock()


def _read_config_dict() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    return loaded if isinstance(loaded, dict) else {}


def update_persisted_config(mutator: Callable[[dict[str, Any]], dict[str, Any] | None]) -> dict[str, Any]:
    """Apply an in-memory config mutation and persist to config.yaml."""
    with _lock:
        data = _read_config_dict()
        updated = mutator(data)
        final_data = updated if isinstance(updated, dict) else data

        with CONFIG_PATH.open("w", encoding="utf-8") as file:
            yaml.safe_dump(final_data, file, sort_keys=False)
        return final_data


def persist_root_path(new_root: str) -> None:
    """Persist directories.root_dir in config.yaml via centralized manager."""
    resolved_root = str(Path(new_root).expanduser().resolve())

    def _mutate(data: dict[str, Any]) -> dict[str, Any]:
        directories = data.get("directories")
        if not isinstance(directories, dict):
            directories = {}
        directories["root_dir"] = resolved_root
        data["directories"] = directories
        return data

    update_persisted_config(_mutate)


def initialize_backends() -> None:
    """Ensure all in-process runtimes are initialized/reloaded once.

    Startup order is always SLPFS first, then Semantixel (if enabled).
    """
    from backend_api.app.semantixel_runtime import rebuild_semantixel_runtime
    from backend_api.app.slpfs_runtime import get_runtime

    with _lock:
        # slpfs_runtime initializes at import; this call validates availability.
        try:
            get_runtime()
        except RuntimeError:
            # Keep backend up even if SLPFS is degraded.
            pass

        # Semantixel runtime is config-gated and rebuilt explicitly.
        rebuild_semantixel_runtime(raise_on_error=False)


def shutdown_backends() -> None:
    """Shut down all backend-managed runtimes in reverse dependency order."""
    from backend_api.app.semantixel_runtime import shutdown_semantixel_runtime
    from backend_api.app.slpfs_runtime import shutdown_runtime

    with _lock:
        shutdown_semantixel_runtime()
        shutdown_runtime()


def get_backend_health_snapshot() -> dict[str, Any]:
    """Return aggregated health across all backend-managed runtimes."""
    from backend_api.app.semantixel_runtime import get_semantixel_health_snapshot
    from backend_api.app.slpfs_runtime import get_runtime_health_snapshot

    slpfs = get_runtime_health_snapshot()
    semantixel = get_semantixel_health_snapshot()

    slpfs_ready = slpfs.get("backend") == "ready"
    sem_enabled = bool(semantixel.get("enabled"))
    sem_ready = bool(semantixel.get("ready"))

    overall_ready = slpfs_ready and ((not sem_enabled) or sem_ready)

    return {
        "status": "healthy" if overall_ready else "degraded",
        "slpfs": slpfs,
        "semantixel": semantixel,
    }
