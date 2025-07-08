import yaml
import logging
from pydantic import BaseModel
from typing import Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models for Configuration ---

class ApiConfig(BaseModel):
    host: str
    port: int

class ServicesConfig(BaseModel):
    quantumpulse_url: str
    vectorstore_url: str

class IgniteConfig(BaseModel):
    addresses: List[str]
    cache_name: str

class RagConfig(BaseModel):
    default_top_k: int
    collection_name: str

class OtelConfig(BaseModel):
    enabled: bool
    endpoint: Optional[str]

class AppConfig(BaseModel):
    """The main configuration model for the H2M service."""
    service_name: str
    version: str
    api: ApiConfig
    services: ServicesConfig
    ignite: IgniteConfig
    rag: RagConfig
    otel: OtelConfig

# --- Configuration Loading ---

_config: Optional[AppConfig] = None

def load_config(path: str = "H2M/config/h2m.yaml") -> AppConfig:
    global _config
    if _config:
        return _config

    try:
        with open(path, "r") as f:
            config_data = yaml.safe_load(f)
        
        _config = AppConfig(**config_data)
        logger.info("H2M configuration loaded and validated successfully.")
        return _config
    except FileNotFoundError:
        logger.error(f"Configuration file not found at path: {path}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error parsing or validating H2M configuration file: {e}", exc_info=True)
        raise

def get_config() -> AppConfig:
    if not _config:
        return load_config()
    return _config

# Load the configuration on module import
config = get_config() 