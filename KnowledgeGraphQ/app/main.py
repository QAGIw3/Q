# KnowledgeGraphQ/app/main.py
from fastapi import FastAPI
from .api import query
from .core.gremlin_client import gremlin_client

app = FastAPI(
    title="KnowledgeGraphQ",
    version="0.1.0",
    description="A service for querying and managing the Q Platform's knowledge graph."
)

@app.on_event("startup")
def startup_event():
    """Connects to the Gremlin server on startup."""
    gremlin_client.connect()

@app.on_event("shutdown")
def shutdown_event():
    """Disconnects from the Gremlin server on shutdown."""
    gremlin_client.close()

app.include_router(query.router, prefix="/query", tags=["Query"])

@app.get("/health", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "graph_connected": gremlin_client.g is not None} 