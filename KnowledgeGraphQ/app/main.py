# KnowledgeGraphQ/app/main.py
from fastapi import FastAPI
import logging
import os

from app.api import query, ingest
from app.core.gremlin_client import gremlin_client
from shared.observability.logging_config import setup_logging
from shared.pulsar_client import shared_pulsar_client

# Configure logging
setup_logging(service_name="KnowledgeGraphQ")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KnowledgeGraphQ API",
    description="Service for storing and querying a graph-based model of the Q platform.",
    version="0.2.0",
)

@app.on_event("startup")
async def startup_event():
    """On startup, connect to the graph database."""
    logger.info("KnowledgeGraphQ starting up...")
    try:
        gremlin_client.connect()
        logger.info("Successfully connected to Gremlin server.")
    except ConnectionError as e:
        # If we can't connect at startup, log a critical error.
        # The service will be unhealthy and should be restarted by Kubernetes.
        logger.critical(f"Fatal: Could not connect to Gremlin server on startup. {e}", exc_info=True)
        # In a real-world scenario, you might want to exit the process
        # import sys; sys.exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown, close the connection."""
    logger.info("KnowledgeGraphQ shutting down...")
    gremlin_client.close()
    shared_pulsar_client.close()

# --- API Routers ---
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["Ingest"])

@app.get("/health", tags=["Health"])
async def health_check():
    # A basic health check. A more advanced one could check the DB connection.
    return {"status": "ok"} 