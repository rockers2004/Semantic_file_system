from typing import Optional
from semantixel.core.config import config
from semantixel.core.logging import logger
from semantixel.providers.clip.hf_provider import HFCLIPProvider
from semantixel.providers.base import OCRProvider, AudioProvider, BaseModelProvider
from semantixel.providers.text.hf_provider import HFTextEmbeddingProvider

try:
    from semantixel.providers.ocr.doctr_provider import DoctrOCRProvider
except ModuleNotFoundError:
    DoctrOCRProvider = None


class NullOCRProvider(OCRProvider):
    """Safe OCR fallback when optional OCR dependencies are unavailable."""

    def load(self):
        return None

    def unload(self):
        return None

    def apply_ocr(self, images, threshold: float = 0.4):
        return [None for _ in images]

class NullAudioProvider(AudioProvider):
    """Safe transcription fallback when optional audio dependencies are unavailable."""

    def load(self):
        return None

    def unload(self):
        return None

    def transcribe(self, file_path: str, max_duration: float = 60.0):
        _ = (file_path, max_duration)
        return None

class NullCLAPProvider(BaseModelProvider):
    """Safe CLAP fallback when optional audio embedding dependencies are unavailable."""

    def load(self):
        return None

    def unload(self):
        return None

    def get_audio_embeddings(self, audio_path: str):
        _ = audio_path
        return [0.0] * 512

    def get_text_embeddings(self, text: str):
        _ = text
        return [0.0] * 512

class ModelManager:
    """
    Singleton manager for all AI models.
    Provides lazy loading and centralized access to model providers.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._clip_provider = None
        self._ocr_provider = None
        self._text_provider = None
        self._audio_provider = None
        self._clap_provider = None
        self._initialized = True

    @property
    def clip(self):
        if self._clip_provider is None:
            provider_type = config.clip.provider
            if provider_type == "HF_transformers":
                self._clip_provider = HFCLIPProvider(checkpoint=config.clip.HF_transformers_clip)
            else:
                # Fallback or other providers like MobileCLIP
                logger.warning(f"Unsupported CLIP provider: {provider_type}. Falling back to HF.")
                self._clip_provider = HFCLIPProvider()
        return self._clip_provider

    @property
    def ocr(self):
        if self._ocr_provider is None:
            provider_type = config.ocr_provider
            if provider_type == "doctr" and DoctrOCRProvider is not None:
                self._ocr_provider = DoctrOCRProvider()
            elif provider_type == "doctr":
                logger.warning("Doctr OCR provider is not installed. OCR will be skipped.")
                self._ocr_provider = NullOCRProvider()
            else:
                logger.warning(f"Unsupported OCR provider: {provider_type}. OCR will be skipped.")
                self._ocr_provider = NullOCRProvider()
        return self._ocr_provider

    @property
    def text_embed(self):
        if self._text_provider is None:
            provider_type = config.text_embed.provider
            if provider_type == "HF_transformers":
                self._text_provider = HFTextEmbeddingProvider(checkpoint=config.text_embed.HF_transformers_embeddings)
            else:
                logger.warning(f"Unsupported Text Embedding provider: {provider_type}. Falling back to HF.")
                self._text_provider = HFTextEmbeddingProvider()
        return self._text_provider

    @property
    def audio(self):
        if self._audio_provider is None:
            provider_type = config.audio.provider
            if provider_type == "faster_whisper":
                try:
                    from semantixel.providers.audio.faster_whisper_provider import FasterWhisperProvider

                    self._audio_provider = FasterWhisperProvider(
                        checkpoint=config.audio.faster_whisper_model
                    )
                except Exception as exc:
                    logger.warning("Audio transcription provider unavailable: %s", exc)
                    self._audio_provider = NullAudioProvider()
            else:
                logger.warning("Unsupported audio provider: %s. Audio transcription disabled.", provider_type)
                self._audio_provider = NullAudioProvider()
        return self._audio_provider

    @property
    def clap(self):
        if self._clap_provider is None:
            try:
                from semantixel.providers.audio.clap_provider import HFAudioCLAPProvider

                self._clap_provider = HFAudioCLAPProvider()
            except Exception as exc:
                logger.warning("CLAP provider unavailable: %s", exc)
                self._clap_provider = NullCLAPProvider()
        return self._clap_provider

    def unload_all(self):
        """Unload all models to free memory/VRAM."""
        for attr in (
            "_clip_provider",
            "_ocr_provider",
            "_text_provider",
            "_audio_provider",
            "_clap_provider",
        ):
            provider = getattr(self, attr, None)
            if provider:
                provider.unload()
                setattr(self, attr, None)

# Global model manager instance
model_manager = ModelManager()
