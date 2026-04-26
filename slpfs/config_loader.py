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
    from .config import SLPFSConfig, MultimodalConfig
except ImportError:
    from config import SLPFSConfig, MultimodalConfig

logger = logging.getLogger(__name__)


def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _as_int(value, default: int, min_value: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and parsed < min_value:
        return default
    return parsed


def _as_float(value, default: float, min_value: float | None = None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and parsed < min_value:
        return default
    return parsed


def _as_list_of_str(value, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return default
    return [item for item in value if isinstance(item, str)]


def load_config_from_yaml(yaml_path: str = "config.yaml") -> SLPFSConfig:
    """Load configuration from YAML file"""
    
    if not os.path.exists(yaml_path):
        logger.warning("Config file not found: %s", yaml_path)
        logger.info("Using default configuration")
        return SLPFSConfig()
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)

        if not isinstance(yaml_config, dict):
            yaml_config = {}
        
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

        multimodal_yaml = yaml_config.get('multimodal', {})
        if isinstance(multimodal_yaml, dict):
            current = config.multimodal
            config.multimodal = MultimodalConfig(
                enabled=_as_bool(multimodal_yaml.get('enabled'), current.enabled),
                db_path=multimodal_yaml.get('db_path', current.db_path),
                include_directories=_as_list_of_str(
                    multimodal_yaml.get('include_directories'),
                    current.include_directories,
                ),
                exclude_directories=_as_list_of_str(
                    multimodal_yaml.get('exclude_directories'),
                    current.exclude_directories,
                ),
                top_k_default=_as_int(
                    multimodal_yaml.get('top_k_default'),
                    current.top_k_default,
                    min_value=1,
                ),
                threshold_default=_as_float(
                    multimodal_yaml.get('threshold_default'),
                    current.threshold_default,
                    min_value=0.0,
                ),
            )
        
        logger.info("Configuration loaded from %s", yaml_path)
        return config
    
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        logger.exception("Error loading config")
        logger.info("Using default configuration")
        return SLPFSConfig()