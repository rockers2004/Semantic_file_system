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
import re
import zipfile
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
MAX_SKIPPED_FILE_DETAILS = 200
KNOWN_ENCRYPTED_EXTENSIONS = {
    ".age",
    ".asc",
    ".enc",
    ".encrypted",
    ".gpg",
    ".hc",
    ".kdbx",
    ".pgp",
    ".pfx",
    ".p12",
    ".tc",
}
PROTECTED_CONTAINER_EXTENSIONS = {
    ".dmg",
    ".sparsebundle",
    ".sparseimage",
}
ARCHIVE_EXTENSIONS = {".zip"}
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".kts", ".scala", ".sh",
    ".ps1", ".sql", ".html", ".css",
}
SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "by", "containing", "contains", "file", "files", "find",
    "for", "in", "inside", "me", "of", "on", "or", "search", "show", "that", "the",
    "to", "with",
}
SEARCH_TOKEN_ALIASES = {
    "logix": "logic",
    "backtracking": "backtrack",
    "backtracked": "backtrack",
    "codes": "code",
    "programs": "program",
}


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

    def _relative_path(self, file_path: str, root_dir: str) -> str:
        try:
            return os.path.relpath(file_path, root_dir)
        except ValueError:
            return os.path.basename(file_path)

    def _file_metadata(
        self,
        file_path: str,
        root_dir: str,
        *,
        current_size: Optional[int] = None,
        current_mtime: Optional[float] = None,
        content_indexed: bool = True,
        security_status: str = "readable",
        skip_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        relative_path = self._relative_path(file_path, root_dir)
        return {
            "file_path": file_path,
            "relative_path": relative_path,
            "file_name": os.path.basename(file_path),
            "file_type": mimetypes.guess_type(file_path)[0] or "unknown",
            "indexed_at": datetime.now().isoformat(),
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "size_bytes": current_size if current_size is not None else 0,
            "modified_ts": current_mtime if current_mtime is not None else 0.0,
            "content_indexed": content_indexed,
            "security_status": security_status,
            "skip_reason": skip_reason or "",
        }

    def _skip_record(
        self,
        file_path: str,
        root_dir: str,
        *,
        status: str,
        reason: str,
        metadata_indexed: bool,
    ) -> Dict[str, Any]:
        return {
            "path": file_path,
            "relative_path": self._relative_path(file_path, root_dir),
            "file_name": os.path.basename(file_path),
            "status": status,
            "reason": reason,
            "metadata_indexed": metadata_indexed,
        }

    def _is_zip_encrypted(self, file_path: str) -> Optional[bool]:
        try:
            with zipfile.ZipFile(file_path) as archive:
                return any(info.flag_bits & 0x1 for info in archive.infolist())
        except zipfile.BadZipFile:
            return None
        except OSError:
            raise
        except Exception:
            logger.exception("Unable to inspect zip encryption status: %s", file_path)
            return None

    def _classify_known_protected_file(self, file_path: str) -> Optional[tuple[str, str]]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in KNOWN_ENCRYPTED_EXTENSIONS:
            return "encrypted_known_extension", f"Known encrypted/sensitive extension: {ext}"
        if ext in PROTECTED_CONTAINER_EXTENSIONS:
            return "possibly_encrypted_container", f"Protected disk image/container extension: {ext}"
        if ext == ".pdf" and PdfReader is not None:
            try:
                reader = PdfReader(file_path)
                if reader.is_encrypted:
                    return "password_required", "Encrypted PDF requires a password"
            except PermissionError:
                raise
            except Exception:
                logger.debug("Unable to inspect PDF encryption status: %s", file_path, exc_info=True)
        if ext in ARCHIVE_EXTENSIONS:
            encrypted = self._is_zip_encrypted(file_path)
            if encrypted:
                return "password_required", "Encrypted zip archive requires a password"
        return None

    def _index_metadata_only(
        self,
        file_path: str,
        root_dir: str,
        *,
        security_status: str,
        reason: str,
        current_size: Optional[int] = None,
        current_mtime: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Index filename/path metadata for protected files without reading content."""
        try:
            if current_size is None:
                try:
                    current_size = os.path.getsize(file_path)
                except OSError:
                    current_size = 0
            if current_mtime is None:
                try:
                    current_mtime = os.path.getmtime(file_path)
                except OSError:
                    current_mtime = 0.0

            metadata = self._file_metadata(
                file_path,
                root_dir,
                current_size=current_size,
                current_mtime=current_mtime,
                content_indexed=False,
                security_status=security_status,
                skip_reason=reason,
            )
            document = (
                f"Protected file metadata only. "
                f"Name: {metadata['file_name']}. Path: {metadata['relative_path']}. "
                f"Status: {security_status}. Reason: {reason}."
            )
            embedding = self.embedding_model.encode(document).tolist()
            self.collection.upsert(
                ids=[self._generate_file_id(file_path)],
                embeddings=[embedding],
                documents=[document],
                metadatas=[metadata],
            )
            logger.warning(
                "Skipped content indexing for protected file; metadata indexed: %s | %s",
                file_path,
                reason,
            )
            return {
                "status": "metadata_indexed",
                "skip": self._skip_record(
                    file_path,
                    root_dir,
                    status=security_status,
                    reason=reason,
                    metadata_indexed=True,
                ),
            }
        except Exception as exc:
            logger.exception("Failed to index protected file metadata: %s", file_path)
            return {
                "status": "error",
                "skip": self._skip_record(
                    file_path,
                    root_dir,
                    status=security_status,
                    reason=f"{reason}; metadata indexing failed: {exc}",
                    metadata_indexed=False,
                ),
            }
    
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

    def _normalize_search_token(self, token: str) -> str:
        token = SEARCH_TOKEN_ALIASES.get(token.lower(), token.lower())
        if len(token) > 5 and token.endswith("ing"):
            token = token[:-3]
        elif len(token) > 4 and token.endswith("ed"):
            token = token[:-2]
        elif len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        return SEARCH_TOKEN_ALIASES.get(token, token)

    def _query_tokens(self, query: str) -> List[str]:
        tokens = []
        for raw in re.findall(r"[a-zA-Z0-9_+#]+", query.lower()):
            token = self._normalize_search_token(raw)
            if token and token not in SEARCH_STOPWORDS:
                tokens.append(token)
        return list(dict.fromkeys(tokens))

    def _is_code_query(self, query: str, tokens: List[str]) -> bool:
        query_lower = query.lower()
        return any(
            marker in tokens or marker in query_lower
            for marker in ("code", "source", "script", "program", "python", ".py")
        )

    def _lexical_search_score(
        self,
        query: str,
        tokens: List[str],
        metadata: Dict[str, Any],
        preview: str,
    ) -> float:
        if not tokens:
            return 0.0

        file_name = str(metadata.get("file_name", "") or "")
        relative_path = str(metadata.get("relative_path", "") or "")
        file_path = str(metadata.get("file_path", "") or "")
        ext = os.path.splitext(file_name)[1].lower()
        is_code_file = ext in CODE_EXTENSIONS
        is_code_query = self._is_code_query(query, tokens)

        content = preview
        if is_code_file and file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
            except OSError:
                content = preview

        haystack = f"{file_name} {relative_path} {content}".lower()
        normalized_haystack = " ".join(
            self._normalize_search_token(token)
            for token in re.findall(r"[a-zA-Z0-9_+#]+", haystack)
        )

        score = 0.0
        generic_terms = {"code", "file", "source", "script", "program", "logic"}
        specific_terms = [token for token in tokens if token not in generic_terms]

        for token in tokens:
            if token in normalized_haystack:
                score += 0.18
            if token in file_name.lower() or token in relative_path.lower():
                score += 0.12

        specific_hits = sum(1 for token in specific_terms if token in normalized_haystack)
        score += specific_hits * 0.35

        if is_code_query:
            score += 0.40 if is_code_file else -0.25

        if specific_terms and specific_hits == 0:
            score -= 0.35

        return score
    
    def index_file_result(self, file_path: str, root_dir: str) -> Dict[str, Any]:
        """Index one file and return detailed status for reporting."""
        try:
            file_id = self._generate_file_id(file_path)
            try:
                current_size = os.path.getsize(file_path)
                current_mtime = os.path.getmtime(file_path)
            except PermissionError as exc:
                return self._index_metadata_only(
                    file_path,
                    root_dir,
                    security_status="locked_permission_denied",
                    reason=str(exc),
                )

            protected = self._classify_known_protected_file(file_path)
            if protected:
                status, reason = protected
                return self._index_metadata_only(
                    file_path,
                    root_dir,
                    security_status=status,
                    reason=reason,
                    current_size=current_size,
                    current_mtime=current_mtime,
                )

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
                        return {"status": "unchanged"}
            except Exception:
                # If lookup fails, fall through to reindex
                pass

            # Read content
            content = self._read_file_content(file_path)
            if not content or content.startswith("[Error"):
                reason = content or "No content could be read"
                return self._index_metadata_only(
                    file_path,
                    root_dir,
                    security_status="unreadable",
                    reason=reason,
                    current_size=current_size,
                    current_mtime=current_mtime,
                )
            
            # Generate embedding
            embed_content = content if len(content) <= MAX_EMBED_CHARS else content[:MAX_EMBED_CHARS]
            embedding = self.embedding_model.encode(embed_content).tolist()
            
            # Prepare metadata
            metadata = self._file_metadata(
                file_path,
                root_dir,
                current_size=current_size,
                current_mtime=current_mtime,
            )
            
            # Add to ChromaDB
            self.collection.upsert(
                ids=[file_id],
                embeddings=[embedding],
                documents=[content[:1000]],  # Store first 1000 chars as preview
                metadatas=[metadata]
            )
            
            return {"status": "indexed"}
        
        except Exception as e: 
            logger.exception("Error indexing %s: %s", file_path, e)
            return {
                "status": "error",
                "skip": self._skip_record(
                    file_path,
                    root_dir,
                    status="index_error",
                    reason=str(e),
                    metadata_indexed=False,
                ),
            }

    def index_file(self, file_path: str, root_dir: str) -> str:
        """Index a single file. Returns a compact status string."""
        return str(self.index_file_result(file_path, root_dir).get("status", "error"))
    
    def index_directory(self, directory:  str) -> Dict[str, Any]:
        """Index all files in directory (skip unchanged)."""
        stats: Dict[str, Any] = {
            "indexed": 0,
            "unchanged": 0,
            "metadata_indexed": 0,
            "skipped": 0,
            "errors": 0,
            "skipped_files": [],
        }
        
        logger.info("Indexing directory: %s", directory)

        def _record_walk_error(error: OSError) -> None:
            path = getattr(error, "filename", "") or str(error)
            logger.warning("Skipped unreadable directory while indexing: %s | %s", path, error)
            stats["skipped"] += 1
            if len(stats["skipped_files"]) < MAX_SKIPPED_FILE_DETAILS:
                stats["skipped_files"].append(
                    {
                        "path": path,
                        "relative_path": self._relative_path(path, directory),
                        "file_name": os.path.basename(path),
                        "status": "locked_directory",
                        "reason": str(error),
                        "metadata_indexed": False,
                    }
                )
        
        for root, dirs, files in os.walk(directory, onerror=_record_walk_error):
            # Skip hidden directories and vector DB
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.'):
                    continue
                
                file_path = os.path.join(root, file)
                result = self.index_file_result(file_path, directory)
                status = result.get("status")
                if status == "indexed":
                    stats["indexed"] += 1
                    logger.debug("Indexed file: %s", os.path.relpath(file_path, directory))
                elif status == "unchanged":
                    stats["unchanged"] += 1
                elif status == "metadata_indexed":
                    stats["metadata_indexed"] += 1
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1

                skip = result.get("skip")
                if isinstance(skip, dict) and len(stats["skipped_files"]) < MAX_SKIPPED_FILE_DETAILS:
                    stats["skipped_files"].append(skip)
        
        logger.info(
            "Indexed: %s | Unchanged: %s | Metadata-only: %s | Skipped: %s | Errors: %s",
            stats["indexed"],
            stats["unchanged"],
            stats["metadata_indexed"],
            stats["skipped"],
            stats["errors"],
        )
        return stats
    
    def search(self, query: str, k: int = 5, keywords: Optional[str] = None) -> List[Dict[str, Any]]:
        """Semantic search for files"""
        try:
            # Enhance query with keywords
            search_query = f"{query} {keywords}" if keywords else query
            query_tokens = self._query_tokens(search_query)
            is_code_query = self._is_code_query(search_query, query_tokens)
            collection_count = self.collection.count()
            if collection_count <= 0:
                return []
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode(search_query).tolist()
            
            # Search in ChromaDB
            results = self.collection. query(
                query_embeddings=[query_embedding],
                n_results=collection_count if is_code_query else min(max(k * 25, 100), collection_count)
            )
            
            # Format results
            formatted_results = []
            if results['ids'] and results['ids'][0]: 
                for i in range(len(results['ids'][0])):
                    metadata = results['metadatas'][0][i]
                    preview = results['documents'][0][i][:200]
                    semantic_score = 1 - results['distances'][0][i] if 'distances' in results else 1.0
                    lexical_score = self._lexical_search_score(
                        search_query,
                        query_tokens,
                        metadata,
                        results['documents'][0][i],
                    )
                    formatted_results.append({
                        "file_path": metadata['file_path'],
                        "file_name": metadata['file_name'],
                        "relative_path": metadata['relative_path'],
                        "preview": preview,
                        "score": semantic_score + lexical_score,
                        "semantic_score": semantic_score,
                    })
            
            formatted_results.sort(key=lambda item: item["score"], reverse=True)
            return formatted_results[:k]
        
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
