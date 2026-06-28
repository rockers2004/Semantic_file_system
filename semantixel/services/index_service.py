"""Index orchestration — coordinates scanning, embedding, and ChromaDB indexing.

The :class:`IndexService` is the top-level coordinator that:

1. Scans configured local directories.
2. Delegates image/video indexing to :class:`ImageIndexer`.
3. Delegates audio/transcription indexing to :class:`AudioIndexer`.
4. Rebuilds the BM25 keyword index.
5. Cleans up stale entries from deleted or renamed files.
"""

import os
from typing import List
from chromadb import PersistentClient
from semantixel.core.config import config
from semantixel.core.logging import logger
from semantixel.media import MediaDescriptor, describe_local_media
from semantixel.media_types import has_audio_modality, has_visual_modality
from semantixel.services.image_indexer import ImageIndexer
from semantixel.services.audio_indexer import AudioIndexer
from semantixel.services.bm25_service import BM25Service
from semantixel.utils.scan_utils import fast_scan_for_media
from semantixel.services.index_cleanup import IndexCleanupService


class IndexService:
    """Top-level orchestrator for media indexing.

    Usage::

        indexer = IndexService()
        indexer.run_full_scan()

    Attributes:
        image_collection: ChromaDB collection for CLIP image embeddings.
        text_collection: ChromaDB collection for text embeddings (OCR, transcripts).
        audio_collection: ChromaDB collection for CLAP audio embeddings.
        bm25_service: Keyword search index.
    """

    def __init__(self, db_path: str = "db"):
        self.db_path = db_path
        self.client = PersistentClient(path=db_path)

        hnsw_config = {
            "space": "cosine",
            "ef_search": 500,
            "ef_construction": 200,
            "M": 32,
        }
        self.image_collection = self.client.get_or_create_collection(
            "images", metadata=hnsw_config
        )
        self.text_collection = self.client.get_or_create_collection(
            "texts", metadata=hnsw_config
        )
        self.audio_collection = self.client.get_or_create_collection(
            "ambient_audio", metadata=hnsw_config
        )
        # Force HNSW params on existing collections too (get_or_create only applies on create)
        for col in (self.image_collection, self.text_collection, self.audio_collection):
            existing = col.metadata or {}
            if existing.get("ef_search") != hnsw_config["ef_search"]:
                col.modify(metadata=hnsw_config)

        self.image_indexer = ImageIndexer(self.image_collection, self.text_collection)
        self.audio_indexer = AudioIndexer(self.text_collection, self.audio_collection)
        self.bm25_service = BM25Service(index_path=os.path.join(db_path, "bm25_index.pkl"))
        self.cleanup_service = IndexCleanupService(self.client, self.bm25_service)

    # Public API

    def run_full_scan(self):
        """Perform a full scan of configured directories and index all media.

        Logs progress at each phase and cleans up stale index entries.
        """
        logger.info("Starting full media scan and index update")
        include_dirs = config.include_directories
        exclude_dirs = config.exclude_directories

        if not include_dirs:
            logger.warning("No include_directories configured. Skipping scan.")
            return

        paths, elapsed = fast_scan_for_media(include_dirs, exclude_dirs)
        media_items = [describe_local_media(path) for path in paths]

        logger.info(
            "Found %d media files in %.2fs", len(media_items), elapsed
        )

        self._index_media(media_items)
        self.cleanup_service.cleanup(
            media_items, self.image_collection, self.text_collection, self.audio_collection
        )

    # Internal — media processing

    def _index_media(self, media_items: List[MediaDescriptor]):
        """Route each item to the appropriate indexer."""
        from tqdm import tqdm

        audio_items = [
            m for m in media_items
            if has_audio_modality(m.locator)
        ]
        visual_items = [
            m for m in media_items
            if has_visual_modality(m.locator)
        ]

        total_tasks = len(visual_items) + len(audio_items)
        with tqdm(total=total_tasks, desc="Indexing media") as pbar:
            self.image_indexer.index_images(
                visual_items,
                google_drive_source=None,
                pbar=pbar,
            )
            self.audio_indexer.index_audio(audio_items, pbar=pbar)

        self.bm25_service.rebuild_from_collection(self.text_collection)
