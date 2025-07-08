from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class Connector(BaseModel):
    id: str = Field(..., description="Unique identifier for the connector, e.g., 'slack-webhook'.")
    name: str = Field(..., description="Human-readable name of the connector, e.g., 'Slack Webhook Notifier'.")
    version: str = Field(..., description="Version of the connector.")
    description: Optional[str] = Field(null=True, description="A brief description of what the connector does.")
    required_config_schema: Dict[str, Any] = Field(..., description="A JSON schema describing the required configuration fields for this connector.") 