from fastapi import FastAPI

from .api import flows, connectors, webhooks, credentials
from .core.pulsar_client import close_pulsar_producer

app = FastAPI(
    title="Cross-Platform Integration Hub",
    description="A plug-and-play service for connecting your AI ecosystem to external APIs, databases, SaaS, and messaging platforms.",
    version="0.1.0",
)

@app.on_event("shutdown")
def shutdown_event():
    close_pulsar_producer()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Integration Hub"}

app.include_router(flows.router, prefix="/flows", tags=["Flows"])
app.include_router(connectors.router, prefix="/connectors", tags=["Connectors"])
app.include_router(webhooks.router, prefix="/hooks", tags=["Webhooks"])
app.include_router(credentials.router, prefix="/credentials", tags=["Credentials"]) 