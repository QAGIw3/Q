from fastapi import FastAPI

from .api import flows, connectors

app = FastAPI(
    title="Cross-Platform Integration Hub",
    description="A plug-and-play service for connecting your AI ecosystem to external APIs, databases, SaaS, and messaging platforms.",
    version="0.1.0",
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Integration Hub"}

app.include_router(flows.router, prefix="/flows", tags=["Flows"])
app.include_router(connectors.router, prefix="/connectors", tags=["Connectors"]) 