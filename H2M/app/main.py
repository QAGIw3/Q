import sys
import os
# Add the shared directory to the path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
import uvicorn
import logging

from app.api import chat
from app.core.config import config
from app.services.ignite_client import ignite_client
# Assuming a shared tracing setup might exist, similar to other services
# from shared.opentelemetry.tracing import setup_tracing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app instance
app = FastAPI(
    title=config.service_name,
    version=config.version,
    description="Human-to-Machine (H2M) service for conversational AI orchestration."
)

# Setup OpenTelemetry if enabled
# if config.otel.enabled:
#     setup_tracing(app)

@app.on_event("startup")
async def startup_event():
    """
    Connects to Apache Ignite on application startup.
    """
    logger.info("Application startup...")
    try:
        await ignite_client.connect()
    except Exception as e:
        logger.critical(f"Could not connect to Ignite on startup: {e}", exc_info=True)
        # Consider exiting if the cache is essential
        # exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    """
    Disconnects from Ignite on application shutdown.
    """
    logger.info("Application shutdown...")
    await ignite_client.disconnect()

# Include the API router
app.include_router(chat.router, prefix="/chat", tags=["Chat"])

@app.get("/health", tags=["Health"])
def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "ok", "ignite_connected": ignite_client.client.is_connected()}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True
    ) 