import yaml
import logging
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models for Configuration ---

class PulsarTopics(BaseModel):
    requests: str
    preprocessed: str
    routed_prefix: str
    results: str
    feedback: str
    analytics: str
    model_updates: str

class PulsarConfig(BaseModel):
    service_url: str
    tls_trust_certs_file_path: Optional[str] = None
    token: Optional[str] = None
    topics: PulsarTopics

class ApiConfig(BaseModel):
    host: str
    port: int

class IgniteConfig(BaseModel):
    addresses: List[str]
    cluster_name: str
    cache_name: str

class ModelShardConfig(BaseModel):
    name: str = Field(..., alias='name')
    shards: List[str]

class FlinkConfig(BaseModel):
    rest_url: str
    prompt_optimizer_jar_path: str
    dynamic_router_jar_path: str

class OtelConfig(BaseModel):
    """Configuration for OpenTelemetry."""
    enabled: bool = True
    endpoint: Optional[str] = "http://localhost:4317" # OTLP gRPC endpoint

class AppConfig(BaseModel):
    """The main configuration model for the application."""
    service_name: str
    version: str
    pulsar: PulsarConfig
    api: ApiConfig
    ignite: IgniteConfig
    models: List[ModelShardConfig]
    flink: FlinkConfig
    otel: OtelConfig = Field(default_factory=OtelConfig)

# --- Configuration Loading ---

_config: Optional[AppConfig] = None

def load_config(path: str = "config/quantumpulse.yaml") -> AppConfig:
    """
    Loads, validates, and returns the application configuration.
    Caches the configuration after the first load.
    """
    global _config
    if _config:
        return _config

    try:
        with open(path, "r") as f:
            config_data = yaml.safe_load(f)
        
        _config = AppConfig(**config_data)
        logger.info("Application configuration loaded and validated successfully.")
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
        return load_config()
    return _config

# Load the configuration on module import
config = get_config() 