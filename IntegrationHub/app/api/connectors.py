from fastapi import APIRouter, HTTPException, Depends
from typing import List

from ..models.connector import Connector, ConnectorMetadata
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

router = APIRouter()

# In-memory database for demonstration purposes
# This would be populated from a registry, e.g., by scanning a directory or a database.
CONNECTORS_DB = {
    "slack-webhook": ConnectorMetadata(
        id="slack-webhook",
        name="Slack Webhook Notifier",
        version="1.0.0",
        description="Sends a message to a Slack channel via an incoming webhook.",
    ),
    "jira-create-issue": ConnectorMetadata(
        id="jira-create-issue",
        name="Jira: Create Issue",
        version="1.0.0",
        description="Creates a new issue in a Jira project.",
    ),
}

@router.get("/", response_model=List[ConnectorMetadata])
def list_connectors(user: UserClaims = Depends(get_current_user)):
    """
    List all available connectors in the marketplace.
    """
    return list(CONNECTORS_DB.values())

@router.get("/{connector_id}", response_model=ConnectorMetadata)
def get_connector(connector_id: str, user: UserClaims = Depends(get_current_user)):
    """
    Retrieve a single connector's details by its ID.
    """
    if connector_id not in CONNECTORS_DB:
        raise HTTPException(status_code=404, detail=f"Connector with ID {connector_id} not found")
    return CONNECTORS_DB[connector_id] 