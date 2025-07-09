from fastapi import FastAPI
import uvicorn
import logging
import structlog

from app.api import ingest, search, management
from app.core.config import config
from app.core.milvus_handler import milvus_handler
from shared.observability.logging_config import setup_logging
from shared.observability.metrics import setup_metrics
# from shared.opentelemetry.tracing import setup_tracing

# --- Logging and Metrics Setup ---
setup_logging()
logger = structlog.get_logger(__name__)

# --- FastAPI App ---
app = FastAPI(
    title=config.service_name,
    version=config.version,
    description="A centralized service for managing and querying vector embeddings."
)

# Setup Prometheus metrics
setup_metrics(app, app_name=config.service_name)

# Setup OpenTelemetry if enabled
# if config.otel.enabled:
#     # A bit of a workaround to make the shared tracer compatible
#     class AppWrapper:
#         def __init__(self, app, service_name, version):
#             self.app = app
#             self.service_name = service_name
#             self.version = version
#             self.otel = config.otel
    
#     setup_tracing(AppWrapper(app, config.service_name, config.version))


@app.on_event("startup")
def startup_event():
    """
    Connects to Milvus on application startup.
    """
    logger.info("Application startup...")
    try:
        milvus_handler.connect()
    except Exception as e:
        logger.critical(f"Could not connect to Milvus on startup. Please check the connection details. Error: {e}", exc_info=True)
        # In a real-world scenario, you might want the app to exit if it can't connect.
        # exit(1)

@app.on_event("shutdown")
def shutdown_event():
    """
    Disconnects from Milvus on application shutdown.
    """
    logger.info("Application shutdown...")
    milvus_handler.disconnect()

# Include the API routers
app.include_router(ingest.router, prefix="/v1/ingest", tags=["Ingestion"])
app.include_router(search.router, prefix="/v1/search", tags=["Search"])
app.include_router(management.router, prefix="/v1/manage", tags=["Management"])

@app.get("/health", tags=["Health"])
def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "ok", "milvus_connected": milvus_handler._connected}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True
    ) 