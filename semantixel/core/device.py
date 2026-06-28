"""Device detection, tensor unwrapping, and GPU memory management utilities.

Provides a single source of truth for PyTorch device selection across all
providers, eliminating the repeated ``if mps/cuda/cpu`` pattern. Also includes
a generic ``unwrap_output`` helper for transformers v5 model outputs and a
``clear_gpu_cache`` helper.
"""

import torch
from typing import Any, Union


def detect_device(prefer_cuda: bool = True) -> str:
    """Detect the best available PyTorch device.

    Priority order:
        1. CUDA (NVIDIA GPU) — if ``prefer_cuda`` is ``True`` and available.
        2. MPS (Apple Silicon) — if CUDA is unavailable.
        3. CPU — fallback.

    Returns:
        A device string suitable for ``torch.device(...)`` or
        ``model.to(...)``.  Always returns ``"cuda"`` (not ``"cuda:0"``)
        for consistency across the codebase.
    """
    if prefer_cuda and torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def detect_device_prefer_cpu() -> str:
    """Detect device forcing CPU preference (used for CPU-only pipelines)."""
    return detect_device(prefer_cuda=False)


def unwrap_output(output: Any) -> torch.Tensor:
    """Extract the primary tensor from a transformers v5 model output.

    Hugging Face ``transformers`` v5 changed several output classes to
    return ``BaseModelOutputWithPooling`` (or similar) instead of raw
    tensors.  This helper normalises them back to a single tensor.

    Args:
        output: A model output — either a dataclass with a ``pooler_output``
            attribute, a raw ``torch.Tensor``, or a tuple/list.

    Returns:
        A ``torch.Tensor``.
    """
    if hasattr(output, "pooler_output"):
        return output.pooler_output
    if isinstance(output, torch.Tensor):
        return output
    return output[0]


def clear_gpu_cache(device: str) -> None:
    """Release unused GPU memory held by PyTorch.

    Safe to call even when *device* is not CUDA — the call is a no-op in
    that case.

    Args:
        device: The device string (e.g. ``"cuda"``, ``"cpu"``).
    """
    if device == "cuda":
        torch.cuda.empty_cache()
