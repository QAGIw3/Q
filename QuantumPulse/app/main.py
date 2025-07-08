from fastapi import FastAPI
import uvicorn
import logging

from app.api.endpoints import inference
from app.core.pulsar_client import PulsarManager
from app.core import pulsar_client as pulsar_manager_module
from app.core.config import config
from shared.opentelemetry.tracing import setup_tracing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app instance
app = FastAPI(
    title=config.service_name,
    version=config.version,
    description="A next-generation service for distributed LLM inference pipelines."
)

# Setup OpenTelemetry
setup_tracing(app)

@app.on_event("startup")
def startup_event():
    """
    Application startup event handler.
    Initializes the Pulsar manager and connects to the cluster.
    """
    logger.info("Application startup...")
    pulsar_manager_module.pulsar_manager = PulsarManager(
        service_url=config.pulsar.service_url,
        token=config.pulsar.token,
        tls_trust_certs_file_path=config.pulsar.tls_trust_certs_file_path
    )
    try:
        pulsar_manager_module.pulsar_manager.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Pulsar on startup: {e}", exc_info=True)
        # Depending on the desired behavior, you might want to exit the application
        # exit(1)

@app.on_event("shutdown")
def shutdown_event():
    """
    Application shutdown event handler.
    Closes the Pulsar client connection.
    """
    logger.info("Application shutdown...")
    if pulsar_manager_module.pulsar_manager:
        pulsar_manager_module.pulsar_manager.close()

# Include the API router
app.include_router(inference.router, prefix="/api", tags=["Inference"])

@app.get("/health", tags=["Health"])
def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True # Use reload for development
    ) 