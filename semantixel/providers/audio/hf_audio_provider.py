"""Hugging Face Transformers Whisper audio transcription provider."""

from typing import Optional
from semantixel.providers.base import AudioProvider
from semantixel.providers.registry import provider
from semantixel.core.logging import logger, log_exception
from semantixel.core.device import detect_device, clear_gpu_cache

try:
    import torch
    from transformers import pipeline
    import transformers as _transformers
    _transformers.logging.set_verbosity_error()
    _HAS_HF_AUDIO_DEPS = True
except ModuleNotFoundError:
    _HAS_HF_AUDIO_DEPS = False


@provider("audio", "HF_transformers")
class HFAudioProvider(AudioProvider):
    """Hugging Face Transformers implementation of Whisper transcription.

    Uses the ``automatic-speech-recognition`` pipeline with chunked
    processing for long audio (30 s chunks).
    """

    def __init__(self, checkpoint: str = "openai/whisper-tiny"):
        self.checkpoint = checkpoint
        self.pipe = None
        self.device_mapped = detect_device().replace("cuda", "cuda:0")

    def load(self):
        """Load the Whisper model into a Hugging Face pipeline."""
        if not _HAS_HF_AUDIO_DEPS:
            logger.warning("HF audio dependencies (torch, transformers) are not installed")
            return
        if self.pipe is not None:
            return

        logger.info(
            "Loading HF Audio model (Whisper): %s on %s",
            self.checkpoint,
            self.device_mapped,
        )

        try:
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=self.checkpoint,
                device=self.device_mapped,
                local_files_only=True,
            )
        except Exception:
            logger.info(
                "Audio model %s not found locally. Downloading...", self.checkpoint
            )
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=self.checkpoint,
                device=self.device_mapped,
            )

    def unload(self):
        """Unload the pipeline and free GPU memory."""
        if self.pipe is not None:
            logger.info("Unloading Audio model")
            self.pipe = None
            clear_gpu_cache(self.device_mapped)

    def transcribe(self, file_path: str, max_duration: float = 60.0) -> Optional[str]:
        """Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file.
            max_duration: Maximum seconds of audio to process
                (``0`` = full file).

        Returns:
            Transcribed text, or ``None`` on failure.
        """
        self.load()
        if self.pipe is None:
            return None
        try:
            import librosa

            duration = None if max_duration <= 0 else max_duration
            y, sr = librosa.load(file_path, sr=16000, duration=duration)

            audio_input = {"raw": y, "sampling_rate": sr}
            result = self.pipe(audio_input, return_timestamps=True, chunk_length_s=30)
            return result.get("text", "").strip()
        except Exception:
            log_exception(logger, "Error transcribing %s", file_path)
            return None
