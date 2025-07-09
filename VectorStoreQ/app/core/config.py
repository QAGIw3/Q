import yaml
import logging
from pydantic import BaseModel, Field
from typing import Optional
from shared.vault_client import VaultClient

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

def load_config() -> AppConfig:
    """
    Loads, validates, and returns the application configuration from Vault.
    """
    global _config
    if _config:
        return _config

    try:
        logger.info("Loading VectorStoreQ configuration from Vault...")
        vault_client = VaultClient(role="vectorstoreq-role")
        config_data = vault_client.read_secret_data("secret/data/vectorstore/config")
        
        _config = AppConfig(**config_data)
        logger.info("VectorStoreQ configuration loaded and validated successfully from Vault.")
        return _config
    except Exception as e:
        logger.error(f"Error loading VectorStoreQ configuration from Vault: {e}", exc_info=True)
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