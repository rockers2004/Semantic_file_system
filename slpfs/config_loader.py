"""
slpfs/config_loader.py


Loads LSFS configuration from a YAML file and maps it onto an LSFSConfig instance.


Provides:
    - load_config_from_yaml() : Reads `config.yaml` (or a custom path) and
      populates an LSFSConfig dataclass with values for directories, Ollama
      settings, embedding model, search parameters, performance options, and
      feature flags. Falls back to LSFSConfig defaults if the file is missing
      or malformed.

Expected top-level YAML keys:
    directories, ollama, embedding, search, performance, features
"""

import yaml
import logging
import os
try:
    from .config import SLPFSConfig
except ImportError:
    from config import SLPFSConfig

logger = logging.getLogger(__name__)


def load_config_from_yaml(yaml_path: str = "config.yaml") -> SLPFSConfig:
    """Load configuration from YAML file"""
    
    if not os.path.exists(yaml_path):
        logger.warning("Config file not found: %s", yaml_path)
        logger.info("Using default configuration")
        return SLPFSConfig()
    
    try:
        with open(yaml_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        config = SLPFSConfig()
        
        # Override with YAML values
        if 'directories' in yaml_config: 
            config.root_dir = yaml_config['directories']. get('root_dir', config.root_dir)
            config.vector_db_dir = yaml_config['directories'].get('vector_db_dir', config. vector_db_dir)
        
        if 'ollama' in yaml_config:
            config.ollama_model = yaml_config['ollama'].get('model', config.ollama_model)
            config.ollama_url = yaml_config['ollama'].get('url', config.ollama_url)
        
        if 'embedding' in yaml_config: 
            config.embedding_model = yaml_config['embedding'].get('model', config.embedding_model)
        
        if 'search' in yaml_config:
            config.default_search_results = yaml_config['search'].get('default_results', config.default_search_results)
            config.max_file_size_mb = yaml_config['search'].get('max_file_size_mb', config.max_file_size_mb)
        
        if 'performance' in yaml_config:
            config.enable_caching = yaml_config['performance'].get('enable_caching', config.enable_caching)
        
        if 'features' in yaml_config:
            config.enable_versioning = yaml_config['features'].get('enable_versioning', False)
            config.enable_redis = yaml_config['features'].get('enable_redis', False)
        
        logger.info("Configuration loaded from %s", yaml_path)
        return config
    
    except Exception as e:
        logger.exception("Error loading config")
        logger.info("Using default configuration")
        return SLPFSConfig()