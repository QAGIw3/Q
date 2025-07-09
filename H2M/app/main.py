import sys
import os
# Add the shared directory to the path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
import uvicorn
import logging
import structlog

from app.api import chat
from app.core.config import config
from app.services.ignite_client import ignite_client
from app.services.h2m_pulsar import h2m_pulsar_client
from app.core.human_feedback import HumanFeedbackListener, human_feedback_listener as hfl_instance
from shared.observability.logging_config import setup_logging
from shared.observability.metrics import setup_metrics

# --- Logging and Metrics Setup ---
setup_logging()
logger = structlog.get_logger(__name__)

# --- FastAPI App ---
app = FastAPI(
    title=config.service_name,
    version=config.version,
    description="Human-to-Machine (H2M) service for conversational AI orchestration."
)

# Setup Prometheus metrics
setup_metrics(app, app_name=config.service_name)

@app.on_event("startup")
async def startup_event():
    """Initializes and starts all background services."""
    global hfl_instance
    logger.info("H2M starting up...")
    try:
        await ignite_client.connect()
        
        hfl_instance = HumanFeedbackListener(
            service_url=config.pulsar.service_url,
            topic=config.pulsar.topics.human_feedback_topic
        )
        hfl_instance.start()
        
        h2m_pulsar_client.start_producer()

    except Exception as e:
        logger.critical(f"Could not initialize H2M services on startup: {e}", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    """Stops all background services gracefully."""
    logger.info("H2M shutting down...")
    await ignite_client.disconnect()
    if hfl_instance:
        hfl_instance.stop()
    h2m_pulsar_client.close()

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