"""Audio indexing service for transcription and CLAP embedding."""

from typing import List, Optional
from tqdm import tqdm
from semantixel.core.config import config
from semantixel.core.logging import logger
from semantixel.media import MediaDescriptor
from semantixel.media_types import (is_audio_file as path_is_audio_file,is_video_file as path_is_video_file,)


class AudioIndexer:
    """Indexes audio content into ChromaDB collections.

    Two parallel indexing paths:

    * **Transcription** — Whisper transcribes speech → MiniLM embeds text.
    * **Ambient** — CLAP embeds the raw audio into a dedicated collection.
    """

    def __init__(self, text_collection, audio_collection):
        self.text_collection = text_collection
        self.audio_collection = audio_collection

    def is_audio_file(self, path: str) -> bool:
        """Check whether *path* is a supported audio format."""
        return path_is_audio_file(path)

    def is_video_file(self, path: str) -> bool:
        """Check whether *path* is a supported video format."""
        return path_is_video_file(path)

    def index_audio(
        self,
        audio_items: List[MediaDescriptor],
        pbar: Optional[tqdm] = None,
    ) -> None:
        """Transcribe and/or embed audio items.

        Args:
            audio_items: Media descriptors for audio files and videos
                (videos may contain audio tracks).
            pbar: Optional progress bar to update.
        """
        audio_config = config.audio
        if not audio_config.enabled:
            if pbar:
                pbar.update(len(audio_items))
            return

        from semantixel.services.model_manager import model_manager

        for media in audio_items:
            is_video = self.is_video_file(media.locator)
            derived_type = "video" if is_video else "audio"

            if self._exceeds_max_duration(media):
                logger.debug(
                    "Skipping %s — exceeds max_duration", media.display_path
                )
                if pbar:
                    pbar.update(1)
                continue

            if audio_config.transcription_enabled:
                self._index_transcription(media, derived_type, model_manager)

            if audio_config.clap_enabled:
                self._index_ambient(media, derived_type, model_manager)

            if pbar:
                pbar.update(1)

    # Internal helpers

    def _exceeds_max_duration(self, media: MediaDescriptor) -> bool:
        """Return ``True`` if the file exceeds the configured max duration.

        Only checked for native audio files (not videos), since ``librosa``
        may not have an MP4 decoder installed on the system.
        """
        max_dur = config.audio.max_duration_seconds
        if max_dur <= 0:
            return False
        if self.is_video_file(media.locator):
            return False
        if not self.is_audio_file(media.locator):
            return False
        try:
            import librosa

            duration = librosa.get_duration(path=media.locator)
            return duration > max_dur
        except Exception:
            return False

    def _index_transcription(
        self, media: MediaDescriptor, derived_type: str, model_manager
    ) -> None:
        """Transcribe and embed speech, then upsert into the text collection."""
        transcript_id = f"{media.media_id}:::audio"

        try:
            existing = self.text_collection.get(ids=[transcript_id])
        except Exception:
            existing = {"ids": []}

        if existing["ids"]:
            return

        try:
            transcript = model_manager.audio.transcribe(
                media.locator, config.audio.transcription_max_duration
            )
        except Exception as exc:
            logger.warning(
                "Transcription failed for %s: %s", media.display_path, exc
            )
            transcript = None

        if not (transcript and transcript.strip()):
            return

        try:
            text_embedding = model_manager.text_embed.get_embeddings(transcript)
            self.text_collection.upsert(
                ids=[transcript_id],
                embeddings=[text_embedding],
                metadatas=[{
                    "source": media.source,
                    "source_media_id": media.media_id,
                    "locator": media.locator,
                    "display_path": media.display_path,
                    "type": derived_type,
                    "subtype": "transcript",
                }],
                documents=[transcript],
            )
        except Exception as exc:
            logger.warning(
                "Transcript embedding/indexing failed for %s: %s",
                media.display_path,
                exc,
            )

    def _index_ambient(
        self, media: MediaDescriptor, derived_type: str, model_manager
    ) -> None:
        """Embed ambient audio via CLAP and upsert into the audio collection."""
        ambient_id = f"{media.media_id}:::ambient"

        try:
            existing = self.audio_collection.get(ids=[ambient_id])
        except Exception:
            existing = {"ids": []}

        if existing["ids"]:
            return

        try:
            ambient_embedding = model_manager.clap.get_audio_embeddings(media.locator)
        except Exception as exc:
            logger.warning(
                "CLAP embedding failed for %s: %s", media.display_path, exc
            )
            return

        self.audio_collection.upsert(
            ids=[ambient_id],
            embeddings=[ambient_embedding],
            metadatas=[{
                "source": media.source,
                "source_media_id": media.media_id,
                "locator": media.locator,
                "display_path": media.display_path,
                "type": derived_type,
                "subtype": "ambient",
            }],
        )
