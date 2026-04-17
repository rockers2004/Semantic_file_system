"""
slpfs/config.py

Defines the SLPFSconfig, the central configuration dataclass for the Local SLPFS.

SLPFSConfig holds all tuneable setting grouped by concern:
    - Directories    : root watched directory and ChromaDB storage path.
    - Ollama         : local LLM model name and server URL.
    - Embedding      : sentence-transformer model used to generate vectors.
    - Search         : default result count and per-file size limit.
    - Performance    : in-memory caching toggle.
    - Feature flags  : versioning and Redis support (both disabled by default).

A module-level `config` instance is provided as a ready-to-use singleton;
it can be replaced at runtime by loading values from `config.yaml` via
`config_loader.load_config_from_yaml()`.
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class MultimodalConfig:
    """Configuration for multimodal indexing and retrieval."""

    enabled: bool = False
    db_path: str = "./db_multimodal"
    include_directories: List[str] = field(default_factory=list)
    exclude_directories: List[str] = field(default_factory=list)
    top_k_default: int = 5
    threshold_default: float = 0.0

@dataclass
class SLPFSConfig:
    """Configuration for Local SLPFS"""
    
    # Directories
    root_dir: str = "C:/Users/Taslim/OneDrive/Desktop/lsfs-test"
    # Where ChromaDB stores its data; keep relative to project root by default.
    vector_db_dir: str = "./.lsfs_db"
    
    # Ollama settings
    ollama_model: str = "qwen3:14b"  # Your 5B model
    ollama_url: str = "http://localhost:11434"
    
    # Embedding model 
    embedding_model: str = "all-mpnet-base-v2"  
    
    # Search settings
    default_search_results: int = 5
    
    # Performance
    enable_caching: bool = True
    max_file_size_mb: int = 10
    
    # Version control (DISABLED - no Redis needed)
    enable_versioning: bool = False
    enable_redis:  bool = False

    # Multimodal settings
    multimodal: MultimodalConfig = field(default_factory=MultimodalConfig)
    
    def __post_init__(self):
        """Create directories if they don't exist"""
        os.makedirs(self.root_dir, exist_ok=True)
        os.makedirs(self.vector_db_dir, exist_ok=True)
        os.makedirs(self.multimodal.db_path, exist_ok=True)

# Global config instance
config = SLPFSConfig()