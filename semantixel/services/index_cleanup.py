"""Index cleanup — removes stale entries for deleted or renamed media files."""

from typing import List, Set
from semantixel.core.logging import logger
from semantixel.media import MediaDescriptor
from semantixel.services.bm25_service import BM25Service


class IndexCleanupService:
    """Compares the current media set against the index and removes orphans.

    An entry is considered **stale** when its ``locator`` (file path) no
    longer exists on disk, or when its source file has been deleted.
    """

    def __init__(self, client, bm25_service: BM25Service):
        self.client = client
        self.bm25_service = bm25_service

    @staticmethod
    def _collect_known_ids(
        image_collection,
        text_collection,
        audio_collection,
    ) -> Set[str]:
        """Gather all media IDs currently in the index.

        Returns:
            A set of ``media_id`` values.
        """
        known: Set[str] = set()
        for coll in (image_collection, text_collection, audio_collection):
            try:
                data = coll.get(include=[])
                known.update(data.get("ids", []))
            except Exception:
                pass
        return known

    def cleanup(
        self,
        current_media: List[MediaDescriptor],
        image_collection,
        text_collection,
        audio_collection,
    ) -> None:
        """Remove entries whose media files no longer exist.

        Args:
            current_media: List of media items that were just scanned.
            image_collection: ChromaDB image embedding collection.
            text_collection: ChromaDB text embedding collection.
            audio_collection: ChromaDB audio embedding collection.
        """
        current_ids: Set[str] = set()
        for media in current_media:
            current_ids.add(media.media_id)
            if media.timestamp is not None:
                current_ids.add(media.composite_id)

        indexed_ids = self._collect_known_ids(
            image_collection, text_collection, audio_collection
        )

        stale_ids = indexed_ids - current_ids
        stale_base_ids: Set[str] = set()

        # Composite IDs (video frames, transcripts, ambient) may derive
        # from a base media_id.  Detect these by checking whether the
        # base media_id parted by ":::" is still valid.
        for sid in stale_ids:
            if ":::" in sid:
                base = sid.split(":::", 1)[0]
                if base not in current_ids:
                    stale_base_ids.add(sid)
            else:
                stale_base_ids.add(sid)

        if not stale_base_ids:
            return

        stale_list = list(stale_base_ids)
        collections = (
            ("image", image_collection),
            ("text", text_collection),
            ("audio", audio_collection),
        )
        successful_collections = []
        failed_collections = []

        for name, coll in collections:
            try:
                coll.delete(ids=stale_list)
            except Exception as exc:
                failed_collections.append(name)
                logger.warning("Cleanup error in %s collection: %s", name, exc)
            else:
                successful_collections.append(name)

        if not failed_collections:
            logger.info("Cleaned up %d stale index entries", len(stale_list))
        elif successful_collections:
            logger.warning(
                "Partially cleaned up %d stale index entries from %s collection(s); "
                "failed collection(s): %s",
                len(stale_list),
                ", ".join(successful_collections),
                ", ".join(failed_collections),
            )
        else:
            logger.warning(
                "Failed to clean up %d stale index entries from any collection",
                len(stale_list),
            )
