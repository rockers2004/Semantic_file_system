"""BM25 full-text keyword search over OCR and transcript content.

Maintains a persistent BM25 index on disk so that keyword matches
survive process restarts.  The index is rebuilt automatically after
each full media scan.
"""

import os
import pickle
from typing import List
from rank_bm25 import BM25Okapi
from semantixel.core.logging import logger


class BM25Service:
    """BM25-based full-text search index for OCR / transcript content.

    Uses the ``rank_bm25`` implementation of the Okapi BM25 algorithm.
    Tokenization is whitespace-based (no stemmer by default).

    Attributes:
        index_path: Path to the pickle file where the index is persisted.
        bm25: The underlying ``BM25Okapi`` instance (``None`` until first rebuild).
        documents: In-memory list of document texts, parallel to :attr:`doc_ids`.
        doc_ids: ChromaDB document IDs, parallel to :attr:`documents`.
    """

    def __init__(self, index_path: str = "db/bm25_index.pkl"):
        self.index_path = index_path
        self.bm25 = None
        self.documents: List[str] = []
        self.doc_ids: List[str] = []
        self.load()

    def load(self):
        """Load a previously-saved BM25 index from disk, or start fresh."""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                    self.bm25 = data.get("bm25")
                    self.documents = data.get("documents", [])
                    self.doc_ids = data.get("doc_ids", [])
                logger.info("Loaded BM25 index with %d documents", len(self.doc_ids))
            except Exception as exc:
                logger.error("Error loading BM25 index: %s. Starting fresh.", exc)
                self.reset()
        else:
            logger.info("Initializing new BM25 index")
            self.reset()

    def reset(self):
        """Clear the in-memory BM25 index."""
        self.bm25 = None
        self.documents = []
        self.doc_ids = []

    def add_document(self, doc_id: str, text: str):
        """Add or update a document in the in-memory index.

        If *doc_id* already exists, *text* is appended (for multi-frame
        videos whose OCR text accumulates).

        Args:
            doc_id: Unique document identifier.
            text: Document text content.
        """
        if not text or not text.strip():
            return

        if doc_id in self.doc_ids:
            idx = self.doc_ids.index(doc_id)
            if text not in self.documents[idx]:
                self.documents[idx] += " " + text
        else:
            self.documents.append(text)
            self.doc_ids.append(doc_id)

    def rebuild(self, save: bool = True):
        """Rebuild BM25 index from the current :attr:`documents` list.

        Args:
            save: Whether to persist to disk after rebuilding.
        """
        if not self.documents:
            logger.warning("No documents to index for BM25")
            return

        tokenized_docs = [doc.lower().split() for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        logger.info("BM25 index rebuilt with %d documents", len(self.documents))

        if save:
            self.save()

    @staticmethod
    def _infer_media_type(doc_id: str) -> str:
        """Infer media type from document ID.

        IDs with no ``:::`` separator are images.  The postfix after
        ``:::`` determines the type: ``"audio"``, ``"video"``, or a
        numeric timestamp (also ``"video"``).
        """
        if ":::" not in doc_id:
            return "image"

        postfix = doc_id.split(":::")[-1]

        if postfix in {"audio", "video"}:
            return postfix

        try:
            float(postfix)
            return "video"
        except ValueError:
            return "unknown"

    def rebuild_from_collection(self, collection, save: bool = True):
        """Rebuild the BM25 index from a ChromaDB collection's stored documents.

        Reads ``ids`` and ``documents`` from the collection, replaces the
        in-memory document store, and calls :meth:`rebuild`. This ensures
        the keyword index always mirrors the current text collection,
        automatically evicting stale entries from renamed or deleted files.

        Args:
            collection: A ChromaDB collection with ``documents`` stored.
            save: Whether to persist the rebuilt index to disk.
        """
        data = collection.get(include=["documents"])
        ids = data.get("ids", [])
        docs = data.get("documents", [])
        self.documents = []
        self.doc_ids = []
        for doc_id, doc_text in zip(ids, docs):
            if doc_text:
                self.documents.append(doc_text)
                self.doc_ids.append(doc_id)
        self.rebuild(save=save)

    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
        media_type: str = "all",
    ) -> List[str]:
        """Search for documents matching the query.

        Args:
            query: Keyword query string.
            top_k: Maximum number of results.
            threshold: Minimum BM25 score (note: BM25 scores are not
                normalised to 0-1, so this is typically left at 0).
            media_type: ``"image"``, ``"video"``, ``"audio"``, or ``"all"``.

        Returns:
            List of matching document IDs, ordered by descending score.
        """
        if self.bm25 is None:
            return []

        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)

        results = []
        for i, score in enumerate(scores):
            if score > 0:
                doc_id = self.doc_ids[i]
                item_type = self._infer_media_type(doc_id)

                if media_type != "all" and media_type != item_type:
                    continue

                results.append((doc_id, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _score in results[:top_k]]

    def save(self):
        """Persist the BM25 index to disk as a pickle."""
        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)
        try:
            with open(self.index_path, "wb") as f:
                pickle.dump(
                    {
                        "bm25": self.bm25,
                        "documents": self.documents,
                        "doc_ids": self.doc_ids,
                    },
                    f,
                )
            logger.info("BM25 index saved to %s", self.index_path)
        except Exception as exc:
            logger.error("Failed to save BM25 index: %s", exc)
