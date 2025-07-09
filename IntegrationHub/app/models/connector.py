from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

class ConnectorMetadata(BaseModel):
    id: str = Field(..., description="Unique identifier for the connector, e.g., 'slack-webhook'.")
    name: str = Field(..., description="Human-readable name of the connector, e.g., 'Slack Webhook Notifier'.")
    version: str = Field("0.1.0", description="Version of the connector.")
    description: Optional[str] = Field(None, description="A brief description of what the connector does.")
    
class ConnectorAction(BaseModel):
    action_id: str
    credential_id: Optional[str] = None
    configuration: Dict[str, Any] = {}

class BaseConnector(ABC):
    """Abstract Base Class for all connectors."""
    
    @property
    @abstractmethod
    def connector_id(self) -> str:
        """A unique identifier for the connector."""
        pass

    @abstractmethod
    async def execute(self, action: ConnectorAction, configuration: Dict[str, Any], data_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Executes a specific action on the connector.
        
        Args:
            action: The action to perform, including credentials and parameters.
            configuration: The specific configuration for this action.
            data_context: The data passed from the previous step in the flow.

        Returns:
            A dictionary containing the output of the action, which will be merged
            into the data context for the next step. Returns None if no output.
        """
        pass 