"""Image and video frame indexing service.

Handles CLIP embedding computation and ChromaDB upsert for visual media
and video frames.
"""

from typing import List, Optional
from semantixel.core.config import config
from semantixel.core.logging import logger
from semantixel.media import MediaDescriptor, describe_local_media
from semantixel.media_types import is_video_file
from semantixel.services.model_manager import model_manager
from semantixel.utils.video_utils import extract_frames_in_memory


class ImageIndexer:
    """Indexes images and video frames into a ChromaDB collection via CLIP.

    Processes images in configurable batch sizes and handles video
    frame extraction with histogram-based deduplication.
    """

    def __init__(self, image_collection, text_collection):
        self.image_collection = image_collection
        self.text_collection = text_collection

    def needs_indexing(self, media: MediaDescriptor, deep_scan: bool = False) -> bool:
        """Check whether *media* is already indexed.

        Args:
            media: Descriptor for the media item.
            deep_scan: If ``False``, skip items already in the DB.

        Returns:
            ``True`` if the item should be indexed.
        """
        path = media.locator
        is_video = is_video_file(path)

        if is_video:
            results = self.image_collection.get(where={"source_media_id": media.media_id})
            return not results["ids"]

        results = self.image_collection.get(ids=[media.media_id])
        return not results["ids"] or deep_scan

    def index_images(
        self,
        visual_items: List[MediaDescriptor],
        google_drive_source=None,
        pbar=None,
        batch_size: Optional[int] = None,
    ) -> None:
        """Embed images and video frames, then upsert into the collection.

        Args:
            visual_items: Media descriptors for images and videos.
            google_drive_source: Optional source for fetching remote images.
            pbar: Optional ``tqdm`` progress bar to update.
            batch_size: Items per batch (defaults to ``config.batch_size``).
        """
        if not visual_items:
            return

        batch_size = batch_size or config.batch_size
        processing_inputs: list = []
        processing_ids: list = []
        processing_metadatas: list = []

        def flush_batch():
            if not processing_inputs:
                return
            logger.debug("Flushing batch of %d items", len(processing_inputs))

            image_embeddings = model_manager.clip.get_image_embeddings(processing_inputs)
            self.image_collection.upsert(
                ids=processing_ids,
                embeddings=image_embeddings,
                metadatas=processing_metadatas,
            )

            ocr_texts = model_manager.ocr.apply_ocr(processing_inputs)
            for idx, text in enumerate(ocr_texts):
                if text:
                    current_id = processing_ids[idx]
                    metadata = processing_metadatas[idx]
                    text_embedding = model_manager.text_embed.get_embeddings(text)
                    self.text_collection.upsert(
                        ids=[current_id],
                        embeddings=[text_embedding],
                        metadatas=[metadata],
                        documents=[text],
                    )

            processing_inputs.clear()
            processing_ids.clear()
            processing_metadatas.clear()

        for media in visual_items:
            path = media.locator
            is_video = is_video_file(path)

            if is_video:
                for frame in extract_frames_in_memory(path):
                    processing_inputs.append(frame["image"])
                    frame_media = describe_local_media(path, timestamp=frame["timestamp"])
                    processing_ids.append(frame_media.composite_id)
                    processing_metadatas.append({
                        "source": frame_media.source,
                        "source_media_id": frame_media.media_id,
                        "locator": frame_media.locator,
                        "display_path": frame_media.display_path,
                        "timestamp": frame["timestamp"],
                        "type": "video_frame",
                    })
                    if len(processing_inputs) >= batch_size:
                        flush_batch()
            else:
                processing_inputs.append(
                    media.locator
                    if media.source == "local"
                    else self._resolve_remote(media, google_drive_source)
                )
                processing_ids.append(media.media_id)
                processing_metadatas.append({
                    "source": media.source,
                    "source_media_id": media.media_id,
                    "locator": media.locator,
                    "display_path": media.display_path,
                    "type": "image",
                })
                if len(processing_inputs) >= batch_size:
                    flush_batch()

            if pbar:
                pbar.update(1)

        flush_batch()

    @staticmethod
    def _resolve_remote(media: MediaDescriptor, google_drive_source=None):
        """Fetch a remote image and return a PIL Image."""
        if google_drive_source and media.source == google_drive_source.SOURCE_NAME:
            return google_drive_source.fetch_image(media.locator)
        raise ValueError("Unsupported media source: %s" % media.source)
