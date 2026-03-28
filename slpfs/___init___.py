"""
slpfs/__init__.py
----------------
Package initializer for the Local LSFS (LLM-based Semantic File System).

Exposes the primary public API:
    - LocalLSFS   : Main file system class for semantic file indexing and search.
    - LSFSConfig  : Configuration dataclass for customizing LSFS behavior.

Powered by Ollama (local LLMs), ChromaDB (vector store), and
the all-MiniLM-L6-v2 embedding model. All processing is local —
no data is sent to the cloud.

Version: 1.0.0
"""

__version__ = "1.0.0"

from .file_system import LocalSLPFS
from .config import SLPFSConfig

__all__ = ['LocalSLPFS', 'SLPFSConfig']