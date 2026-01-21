import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class LSFSConfig:
    """Configuration for Local LSFS"""
    
    # Directories
    root_dir: str = "C:/Users/Taslim/OneDrive/Desktop/lsfs-test"
    # Where ChromaDB stores its data; keep relative to project root by default.
    vector_db_dir: str = "./.lsfs_db"
    
    # Ollama settings
    ollama_model: str = "llama3.2:3b"  # Your 3B model
    ollama_url: str = "http://localhost:11434"
    
    # Embedding model (lightweight)
    embedding_model: str = "all-MiniLM-L6-v2"  # 80MB, fast
    
    # Search settings
    default_search_results: int = 5
    
    # Performance
    enable_caching: bool = True
    max_file_size_mb: int = 10
    
    # Version control (DISABLED - no Redis needed)
    enable_versioning: bool = False
    enable_redis:  bool = False
    
    def __post_init__(self):
        """Create directories if they don't exist"""
        os.makedirs(self.root_dir, exist_ok=True)
        os.makedirs(self.vector_db_dir, exist_ok=True)

# Global config instance
config = LSFSConfig()