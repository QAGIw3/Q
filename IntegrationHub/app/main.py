from fastapi import FastAPI
import uvicorn
import structlog

from app.api import connectors, credentials, flows, webhooks
from app.core.engine import engine
from app.core.config import config
from shared.observability.logging_config import setup_logging
from shared.observability.metrics import setup_metrics

# --- Logging and Metrics Setup ---
setup_logging()
logger = structlog.get_logger(__name__)

# --- FastAPI App ---
app = FastAPI(
    title="IntegrationHub",
    version="0.1.0",
    description="A service for connecting to and synchronizing with external systems."
)

# Setup Prometheus metrics
setup_metrics(app, app_name="IntegrationHub")

@app.on_event("startup")
async def startup_event():
    logger.info("IntegrationHub starting up...")
    # In a real scenario, you might initialize connections or start background tasks here.
    pass

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("IntegrationHub shutting down...")
    # Clean up any resources here.
    pass

# --- API Routers ---
app.include_router(connectors.router, prefix="/connectors", tags=["Connectors"])
app.include_router(credentials.router, prefix="/credentials", tags=["Credentials"])
app.include_router(flows.router, prefix="/flows", tags=["Flows"])
app.include_router(webhooks.router, prefix="/hooks", tags=["Webhooks"])

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True
    ) 