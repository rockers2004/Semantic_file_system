import yaml
import os
from . config import LSFSConfig

def load_config_from_yaml(yaml_path: str = "config.yaml") -> LSFSConfig:
    """Load configuration from YAML file"""
    
    if not os.path.exists(yaml_path):
        print(f"⚠️  Config file not found: {yaml_path}")
        print("📝 Using default configuration")
        return LSFSConfig()
    
    try:
        with open(yaml_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        config = LSFSConfig()
        
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
        
        print(f"✅ Configuration loaded from {yaml_path}")
        return config
    
    except Exception as e: 
        print(f"❌ Error loading config: {e}")
        print("📝 Using default configuration")
        return LSFSConfig()