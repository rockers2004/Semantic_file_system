"""
slpfs/vector_store.py

Vector Store and Semantic Indexing Layer for Local SLPFS.

This module manages embedding generation, persistent vector storage, and
semantic retrieval for file content using SentenceTransformers and ChromaDB.

Responsibilities:
   - Initialize a persistent ChromaDB collection for file embeddings
   - Read file content safely with size/error guards
   - Index individual files with metadata and change detection
   - Recursively index directories while skipping hidden entries
   - Perform semantic search with optional keyword augmentation
   - Remove file entries from the index and expose index statistics
"""
import hashlib
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import mimetypes
import logging
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

    
logger = logging.getLogger(__name__)


INDEX_SCHEMA_VERSION = 3
MAX_EMBED_CHARS = 50000
LARGE_PDF_MAX_PAGES = 40


class VectorStore:
    """Handles embeddings and semantic search using ChromaDB"""
    
    def __init__(self, db_path: str, embedding_model: str, max_file_size_mb: int = 10):
        logger.info("Initializing vector store at %s...", db_path)
        self.max_file_size_mb = max_file_size_mb
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize embedding model
        logger.info("Loading embedding model: %s", embedding_model)
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Create default collection
        self.collection_name = "lsfs_files"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "LSFS file embeddings"}
        )
        
        logger.info("Vector store ready")
    
    def _generate_file_id(self, file_path: str) -> str:
        """Generate unique ID for file"""
        return hashlib.md5(file_path.encode()).hexdigest()
    
    def _read_pdf_content(self, file_path: str, max_pages: Optional[int] = None) -> Optional[str]:
        """Extract text content from PDF files."""
        if PdfReader is None:
            logger.error("pypdf is not installed; cannot index PDF: %s", file_path)
            return "[PDF parsing unavailable: install pypdf]"

        try:
            reader = PdfReader(file_path)
            pages_text: List[str] = []
            for idx, page in enumerate(reader.pages):
                if max_pages is not None and idx >= max_pages:
                    break
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text)

            if not pages_text:
                return "[Empty PDF or scanned PDF with no extractable text]"

            return "\n\n".join(pages_text)
        except Exception as e:
            logger.error("Error reading PDF %s: %s", file_path, e)
            return f"[Error reading PDF: {str(e)}]"

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Safely read file content"""
        try:
            _, ext = os.path.splitext(file_path)

            # Check file size
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb and ext.lower() != ".pdf":
                return f"[Large file: {file_size_mb:.2f}MB - content not indexed]"

            if ext.lower() == ".pdf":
                if file_size_mb > self.max_file_size_mb:
                    logger.warning(
                        "Large PDF detected (%s MB). Indexing first %s pages only: %s",
                        round(file_size_mb, 2),
                        LARGE_PDF_MAX_PAGES,
                        file_path,
                    )
                    return self._read_pdf_content(file_path, max_pages=LARGE_PDF_MAX_PAGES)
                return self._read_pdf_content(file_path)
            
            # Try to read as text
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return content if content. strip() else "[Empty file]"
        
        except Exception as e:
            logger.error("Error reading file %s: %s", file_path, e)
            return f"[Error reading file: {str(e)}]"
    
    def index_file(self, file_path: str, root_dir: str) -> str:
        """Index a single file. Returns 'indexed', 'unchanged', or 'error'."""
        try:
            file_id = self._generate_file_id(file_path)
            current_size = os.path.getsize(file_path)
            current_mtime = os.path.getmtime(file_path)

            # Check if already indexed and unchanged
            try:
                existing = self.collection.get(ids=[file_id], include=["metadatas"])
                if existing and existing.get("ids") and existing["ids"][0]:
                    meta = existing.get("metadatas", [[]])[0][0] if existing.get("metadatas") else {}
                    stored_size = int(meta.get("size_bytes", -1)) if meta else -1
                    stored_mtime = float(meta.get("modified_ts", -1)) if meta else -1
                    stored_schema_version = int(meta.get("index_schema_version", 0)) if meta else 0
                    if (
                        stored_schema_version == INDEX_SCHEMA_VERSION
                        and stored_size == current_size
                        and abs(stored_mtime - current_mtime) < 1e-6
                    ):
                        return "unchanged"
            except Exception:
                # If lookup fails, fall through to reindex
                pass

            # Read content
            content = self._read_file_content(file_path)
            if not content or content.startswith("[Error"):
                return "error"
            
            # Generate embedding
            embed_content = content if len(content) <= MAX_EMBED_CHARS else content[:MAX_EMBED_CHARS]
            embedding = self.embedding_model.encode(embed_content).tolist()
            
            # Prepare metadata
            relative_path = os.path.relpath(file_path, root_dir)
            metadata = {
                "file_path": file_path,
                "relative_path": relative_path,
                "file_name": os.path.basename(file_path),
                "file_type": mimetypes.guess_type(file_path)[0] or "unknown",
                "indexed_at": datetime.now().isoformat(),
                "index_schema_version": INDEX_SCHEMA_VERSION,
                "size_bytes": current_size,
                "modified_ts": current_mtime,
            }
            
            # Add to ChromaDB
            self.collection.upsert(
                ids=[file_id],
                embeddings=[embedding],
                documents=[content[:1000]],  # Store first 1000 chars as preview
                metadatas=[metadata]
            )
            
            return "indexed"
        
        except Exception as e: 
            logger.exception("Error indexing %s: %s", file_path, e)
            return "error"
    
    def index_directory(self, directory:  str) -> Dict[str, int]:
        """Index all files in directory (skip unchanged)."""
        stats = {"indexed": 0, "unchanged": 0, "errors": 0}
        
        logger.info("Indexing directory: %s", directory)
        
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories and vector DB
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.'):
                    continue
                
                file_path = os.path.join(root, file)
                status = self.index_file(file_path, directory)
                if status == "indexed":
                    stats["indexed"] += 1
                    logger.debug("Indexed file: %s", os.path.relpath(file_path, directory))
                elif status == "unchanged":
                    stats["unchanged"] += 1
                else:
                    stats["errors"] += 1
        
        logger.info(
            "Indexed: %s | Unchanged: %s | Errors: %s",
            stats["indexed"],
            stats["unchanged"],
            stats["errors"],
        )
        return stats
    
    def search(self, query: str, k: int = 5, keywords: Optional[str] = None) -> List[Dict[str, Any]]:
        """Semantic search for files"""
        try:
            # Enhance query with keywords
            search_query = f"{query} {keywords}" if keywords else query
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode(search_query).tolist()
            
            # Search in ChromaDB
            results = self.collection. query(
                query_embeddings=[query_embedding],
                n_results=min(k, self.collection.count())
            )
            
            # Format results
            formatted_results = []
            if results['ids'] and results['ids'][0]: 
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        "file_path": results['metadatas'][0][i]['file_path'],
                        "file_name": results['metadatas'][0][i]['file_name'],
                        "relative_path": results['metadatas'][0][i]['relative_path'],
                        "preview": results['documents'][0][i][:200],
                        "score": 1 - results['distances'][0][i] if 'distances' in results else 1.0
                    })
            
            return formatted_results
        
        except Exception as e: 
            logger.exception("Search error")
            return []
    
    def remove_file(self, file_path: str) -> bool:
        """Remove file from index"""
        try:
            file_id = self._generate_file_id(file_path)
            self.collection.delete(ids=[file_id])
            return True
        except Exception as e:
            logger.exception("Error removing file: %s", file_path)
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        return {
            "total_files": self. collection.count(),
            "collection_name": self.collection_name
        }