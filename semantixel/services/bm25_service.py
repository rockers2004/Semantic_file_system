import os
import pickle
from typing import List
from rank_bm25 import BM25Okapi
from semantixel.core.logging import logger

class BM25Service:
    """
    BM25-based full-text search index for OCR content.
    Better than semantic embeddings for keyword matching.
    """
    
    def __init__(self, index_path="db/bm25_index.pkl"):
        self.index_path = index_path
        self.bm25 = None
        self.documents = []  # Mapping: index -> text
        self.doc_ids = []     # Mapping: index -> doc_id
        self.load()
    
    def load(self):
        """Load existing index or initialize new one"""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'rb') as f:
                    data = pickle.load(f)
                    self.bm25 = data.get('bm25')
                    self.documents = data.get('documents', [])
                    self.doc_ids = data.get('doc_ids', [])
                logger.info(f"Loaded BM25 index with {len(self.doc_ids)} documents")
            except Exception as e:
                logger.error(f"Error loading BM25 index: {e}. Starting fresh.")
                self._reset()
        else:
            logger.info("Initializing new BM25 index")
            self._reset()
    
    def _reset(self):
        self.bm25 = None
        self.documents = []
        self.doc_ids = []
    
    def add_document(self, doc_id: str, text: str):
        """Add or update a document in the index"""
        if not text or not text.strip():
            return
        
        # If document already exists, update it (append for multi-frame videos)
        if doc_id in self.doc_ids:
            idx = self.doc_ids.index(doc_id)
            if text not in self.documents[idx]:
                self.documents[idx] += " " + text
        else:
            self.documents.append(text)
            self.doc_ids.append(doc_id)
    
    def rebuild(self, save: bool = True):
        """Rebuild BM25 index from documents"""
        if not self.documents:
            logger.warning("No documents to index for BM25")
            return
        
        # Tokenize all documents (simple whitespace tokenization for now)
        tokenized_docs = [doc.lower().split() for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        logger.info(f"BM25 index rebuilt with {len(self.documents)} documents")
        
        if save:
            self.save()
    
    def search(self, query: str, top_k: int = 5, threshold: float = 0.0, media_type: str = "all") -> List[str]:
        """
        Search for documents matching the query.
        """
        if self.bm25 is None:
            return []
        
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)
        
        results = []
        for i, score in enumerate(scores):
            # Relax threshold for BM25 scores (not 0-1)
            if score > 0:
                doc_id = self.doc_ids[i]
                is_video = ":::" in doc_id
                
                if media_type == "image" and is_video:
                    continue
                if media_type == "video" and not is_video:
                    continue
                    
                results.append((doc_id, score))
                
        results.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, score in results[:top_k]]
    
    def save(self):
        """Persist index to disk"""
        os.makedirs(os.path.dirname(self.index_path) or '.', exist_ok=True)
        try:
            with open(self.index_path, 'wb') as f:
                pickle.dump({
                    'bm25': self.bm25,
                    'documents': self.documents,
                    'doc_ids': self.doc_ids
                }, f)
            logger.info(f"BM25 index saved to {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")
