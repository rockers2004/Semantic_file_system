"""Backend runtime manager.

Coordinates all in-process runtimes owned by this backend process:
- SLPFS runtime bootstrap (slpfs_runtime.py)
- Semantixel multimodal runtime bootstrap (semantixel_runtime.py)
"""

from __future__ import annotations

from threading import RLock
from typing import Any

from backend_api.app.slpfs_runtime import get_runtime, get_runtime_health_snapshot
from backend_api.app.semantixel_runtime import (
    get_semantixel_health_snapshot,
    rebuild_semantixel_runtime,
)


_lock = RLock()


def initialize_backends() -> None:
    """Ensure all in-process runtimes are initialized/reloaded once."""
    with _lock:
        # slpfs_runtime initializes at import; this call validates availability.
        try:
            get_runtime()
        except RuntimeError:
            # Keep backend up even if SLPFS is degraded.
            pass

        # Semantixel runtime is config-gated and rebuilt explicitly.
        rebuild_semantixel_runtime(raise_on_error=False)


def get_backend_health_snapshot() -> dict[str, Any]:
    """Return aggregated health across all backend-managed runtimes."""
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
