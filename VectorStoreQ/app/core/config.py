import yaml
import logging
from pydantic import BaseModel, Field
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models for Configuration ---

class ApiConfig(BaseModel):
    host: str
    port: int

class MilvusConfig(BaseModel):
    host: str
    port: int
    token: Optional[str] = None
    alias: str = "default"

class OtelConfig(BaseModel):
    enabled: bool
    endpoint: Optional[str]

class AppConfig(BaseModel):
    """The main configuration model for the VectorStoreQ service."""
    service_name: str
    version: str
    api: ApiConfig
    milvus: MilvusConfig
    otel: OtelConfig

# --- Configuration Loading ---

_config: Optional[AppConfig] = None

def load_config(path: str = "config/vectorstore.yaml") -> AppConfig:
    """
    Loads, validates, and returns the application configuration.
    """
    global _config
    if _config:
        return _config

    try:
        with open(path, "r") as f:
            config_data = yaml.safe_load(f)
        
        _config = AppConfig(**config_data)
        logger.info("VectorStoreQ configuration loaded and validated successfully.")
        return _config
    except FileNotFoundError:
        logger.error(f"Configuration file not found at path: {path}", exc_info=True)
        raise
    except (yaml.YAMLError, TypeError, ValueError) as e:
        logger.error(f"Error parsing or validating configuration file: {e}", exc_info=True)
        raise

def get_config() -> AppConfig:
    """
    Dependency injector style function to get the loaded configuration.
    """
    if not _config:
        # Load it with default path
        return load_config()
    return _config

# Load the configuration on module import to make it accessible globally
config = get_config() 