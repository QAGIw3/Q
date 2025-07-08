from fastapi import APIRouter, HTTPException
from typing import List

from ..models.connector import Connector

router = APIRouter()

# In-memory database for demonstration purposes
# This would be populated from a registry, e.g., by scanning a directory or a database.
CONNECTORS_DB = {
    "slack-webhook": Connector(
        id="slack-webhook",
        name="Slack Webhook Notifier",
        version="1.0.0",
        description="Sends a message to a Slack channel via an incoming webhook.",
        required_config_schema={
            "type": "object",
            "properties": {
                "webhook_url": {"type": "string", "title": "Slack Webhook URL"},
                "message": {"type": "string", "title": "Message to send"}
            },
            "required": ["webhook_url", "message"],
        },
    ),
    "jira-create-issue": Connector(
        id="jira-create-issue",
        name="Jira: Create Issue",
        version="1.0.0",
        description="Creates a new issue in a Jira project.",
        required_config_schema={
            "type": "object",
            "properties": {
                "server_url": {"type": "string", "title": "Jira Server URL"},
                "project_key": {"type": "string", "title": "Jira Project Key"},
                "summary": {"type": "string", "title": "Issue Summary"},
                "issue_type": {"type": "string", "title": "Issue Type", "default": "Task"},
            },
            "required": ["server_url", "project_key", "summary"],
        },
    ),
}

@router.get("/", response_model=List[Connector])
def list_connectors():
    """
    List all available connectors in the marketplace.
    """
    return list(CONNECTORS_DB.values())

@router.get("/{connector_id}", response_model=Connector)
def get_connector(connector_id: str):
    """
    Retrieve a single connector's details by its ID.
    """
    if connector_id not in CONNECTORS_DB:
        raise HTTPException(status_code=404, detail=f"Connector with ID {connector_id} not found")
    return CONNECTORS_DB[connector_id] 