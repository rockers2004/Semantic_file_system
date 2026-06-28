"""CLAP audio/text embedding provider via Hugging Face Transformers."""

import torch
import librosa
from typing import List, Union
from transformers import ClapModel, ClapProcessor
from semantixel.providers.base import BaseModelProvider
from semantixel.providers.registry import provider
from semantixel.core.logging import logger
from semantixel.utils import has_audio_stream
from semantixel.core.device import detect_device, unwrap_output, clear_gpu_cache

DEFAULT_CLAP_CHECKPOINT = "laion/clap-htsat-unfused"


@provider("clap", "HF_transformers")
class HFAudioCLAPProvider(BaseModelProvider):
    """CLAP (Contrastive Language-Audio Pretraining) provider.

    Generates aligned audio and text embeddings in a shared latent space,
    enabling text-to-audio and audio-to-audio retrieval.
    """

    def __init__(self, checkpoint: str = DEFAULT_CLAP_CHECKPOINT):
        super().__init__()
        self.checkpoint = checkpoint
        self.processor = None
        self.model = None
        self.is_loaded = False
        self.device = detect_device()

    def load(self):
        """Load the CLAP model and processor onto the selected device."""
        try:
            logger.info(
                "Loading CLAP model: %s on %s", self.checkpoint, self.device
            )
            self.processor = ClapProcessor.from_pretrained(self.checkpoint)
            self.model = ClapModel.from_pretrained(self.checkpoint).to(self.device)
            self.model.eval()
            self.is_loaded = True
            logger.info("Successfully loaded CLAP model: %s", self.checkpoint)
        except Exception as exc:
            logger.error("Failed to load CLAP model %s: %s", self.checkpoint, exc)
            raise

    def get_audio_embeddings(self, audio_path: str) -> list:
        """Compute L2-normalised CLAP audio embedding for a file.

        Args:
            audio_path: Path to an audio file.

        Returns:
            A 512-dimensional embedding vector.  Returns a zero vector
            when the file has no audio stream or processing fails.
        """
        if not self.is_loaded:
            self.load()

        try:
            if not has_audio_stream(audio_path):
                logger.debug(
                    "No audio stream found in %s, skipping CLAP embedding", audio_path
                )
                return [0.0] * 512

            y, sr = librosa.load(audio_path, sr=48000, duration=10.0, res_type="kaiser_fast")
            inputs = self.processor(
                audio=y, sampling_rate=48000, return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model.get_audio_features(**inputs)
                embedding = unwrap_output(outputs)

            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            return embedding[0].cpu().numpy().tolist()

        except Exception as exc:
            logger.warning(
                "CLAP audio embedding failed for %s: %s", audio_path, exc
            )
            return [0.0] * 512

    def get_text_embeddings(self, text: str) -> list:
        """Compute L2-normalised CLAP text embedding.

        Args:
            text: A text query describing sound.

        Returns:
            A 512-dimensional embedding vector.
        """
        if not self.is_loaded:
            self.load()

        try:
            inputs = self.processor(text=text, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.model.get_text_features(**inputs)
                embedding = unwrap_output(outputs)

            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            return embedding[0].cpu().numpy().tolist()
        except Exception as exc:
            logger.error("Error getting CLAP text embedding for '%s': %s", text, exc)
            return [0.0] * 512

    def unload(self):
        """Unload model and free GPU memory."""
        if self.is_loaded:
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            self.is_loaded = False
            clear_gpu_cache(self.device)
            logger.info("Unloaded CLAP model: %s", self.checkpoint)
