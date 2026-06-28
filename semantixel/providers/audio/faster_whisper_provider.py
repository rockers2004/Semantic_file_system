"""Faster-Whisper (CTranslate2) audio transcription provider."""

import torch
from typing import Optional
from semantixel.providers.base import AudioProvider
from semantixel.providers.registry import provider
from semantixel.core.logging import logger
from semantixel.utils import has_audio_stream
from semantixel.core.device import detect_device, clear_gpu_cache

DEFAULT_WHISPER_CHECKPOINT = "tiny.en"


@provider("audio", "faster_whisper")
class FasterWhisperProvider(AudioProvider):
    """Faster-Whisper (CTranslate2) implementation of audio transcription.

    Offers significantly faster inference than the vanilla HF pipeline
    on both CUDA and CPU.  Automatically falls back from ``float16`` to
    ``int8`` on CUDA if a cuBLAS error is encountered.
    """

    def __init__(self, checkpoint: str = DEFAULT_WHISPER_CHECKPOINT):
        self.checkpoint = checkpoint
        self.model = None
        self.device = detect_device()
        self.compute_type = "float16" if self.device == "cuda" else "int8"

    def load(self):
        """Load the Faster-Whisper model."""
        if self.model is not None:
            return

        logger.info(
            "Loading Faster Whisper model: %s on %s (%s)",
            self.checkpoint,
            self.device,
            self.compute_type,
        )

        try:
            from faster_whisper import WhisperModel

            self.model = WhisperModel(
                self.checkpoint, device=self.device, compute_type=self.compute_type
            )
        except Exception as exc:
            logger.error("Failed to load Faster Whisper model: %s", exc)
            raise

    def unload(self):
        """Unload model and free GPU memory."""
        if self.model is not None:
            logger.info("Unloading Faster Whisper model")
            self.model = None
            clear_gpu_cache(self.device)

    def transcribe(self, file_path: str, max_duration: float = 60.0) -> Optional[str]:
        """Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file.
            max_duration: Maximum seconds to process (``0`` = full file).

        Returns:
            Transcribed text, or ``None`` on failure.
        """
        self.load()
        try:
            import librosa

            if not has_audio_stream(file_path):
                logger.debug(
                    "No audio stream found in %s, skipping transcription", file_path
                )
                return None

            duration = None if max_duration <= 0 else max_duration
            y, sr = librosa.load(file_path, sr=16000, duration=duration)

            segments, _ = self.model.transcribe(y, beam_size=5)

            text = " ".join(segment.text for segment in segments)
            return text.strip()

        except Exception as exc:
            exc_lower = str(exc).lower()
            if "cublas" in exc_lower and self.device == "cuda":
                logger.warning(
                    "CUDA transcription failed: %s. Retrying on CPU fallback.", exc
                )
                self.unload()
                self.device = "cpu"
                self.compute_type = "int8"
                return self.transcribe(file_path, max_duration)

            logger.warning(
                "Transcription failed for %s: %s", file_path, exc
            )
            return None
