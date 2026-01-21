"""
Local LSFS - LLM-based Semantic File System
A lightweight, local-first semantic file system powered by Ollama
"""

__version__ = "1.0.0"

from .file_system import LocalLSFS
from .config import LSFSConfig

__all__ = ['LocalLSFS', 'LSFSConfig']