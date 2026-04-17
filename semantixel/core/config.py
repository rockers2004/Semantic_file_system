import os
import yaml
import shutil
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class CLIPConfig(BaseModel):
    HF_transformers_clip: str = "openai/clip-vit-base-patch32"
    mobileclip_checkpoint: str = "mobileclip_s0"
    provider: str = "HF_transformers"

class TextEmbedConfig(BaseModel):
    HF_transformers_embeddings: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_gguf: str = ""
    ollama_embeddings: str = ""
    openai_api_key: str = ""
    openai_endpoint: str = ""
    openai_model: str = ""
    provider: str = "HF_transformers"

class SemantixelConfig(BaseSettings):
    batch_size: int = 16
    clip: CLIPConfig = Field(default_factory=CLIPConfig)
    deep_scan: bool = True
    exclude_directories: List[str] = Field(default_factory=list)
    include_directories: List[str] = Field(default_factory=list)
    ocr_provider: str = "doctr"
    port: int = 23107
    scan_method: str = "default"
    text_embed: TextEmbedConfig = Field(default_factory=TextEmbedConfig)

    model_config = SettingsConfigDict(
        env_prefix="SEMANTIXEL_",
        env_nested_delimiter="__",
        case_sensitive=False
    )

def load_config(config_path: str = "config.yaml", default_path: str = "config.default.yaml") -> SemantixelConfig:
    """
    Loads configuration from a YAML file, falling back to defaults if necessary.
    Automatically creates the config file from the default if it doesn't exist.
    """
    if not os.path.exists(config_path):
        if os.path.exists(default_path):
            print(f"Config file not found. Creating {config_path} from {default_path}")
            shutil.copy(default_path, config_path)
        else:
            # If even default is missing, we just return the default Pydantic model
            # and maybe save it as config.yaml?
            print(f"Warning: Neither {config_path} nor {default_path} found. Using system defaults.")
            return SemantixelConfig()

    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f) or {}
    
    return SemantixelConfig(**config_data)

# Global config instance
config = load_config()
