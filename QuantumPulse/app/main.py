from fastapi import FastAPI
import uvicorn
import logging
import structlog

from app.api.endpoints import inference, fine_tuning, chat
from app.core.pulsar_client import PulsarManager
from app.core import pulsar_client as pulsar_manager_module
from app.core.config import config
from shared.opentelemetry.tracing import setup_tracing
from shared.observability.logging_config import setup_logging
from shared.observability.metrics import setup_metrics

# --- Logging and Metrics Setup ---
setup_logging()
logger = structlog.get_logger(__name__)

# --- FastAPI App ---
app = FastAPI(
    title="QuantumPulse",
    version="0.2.0",
    description="A unified service for LLM inference, routing, and fine-tuning."
)

# Setup Prometheus metrics
setup_metrics(app, app_name=config.service_name)

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

# --- API Routers ---
app.include_router(inference.router, prefix="/v1/inference", tags=["Inference"])
app.include_router(fine_tuning.router, prefix="/v1/fine-tune", tags=["Fine-Tuning"])
app.include_router(chat.router, prefix="/v1/chat", tags=["Chat"])

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