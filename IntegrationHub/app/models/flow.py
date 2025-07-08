from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid

class FlowStep(BaseModel):
    name: str = Field(..., description="Name of the step.")
    connector_id: str = Field(..., description="The ID of the connector to use for this step.")
    configuration: Dict[str, Any] = Field({}, description="Non-secret configuration values for the connector.")
    credential_id: Optional[str] = Field(default=None, description="The ID of the credential to use for this step, if any.")

class FlowTrigger(BaseModel):
    type: str = Field(..., description="Type of trigger, e.g., 'webhook', 'schedule', 'pulsar'.")
    configuration: Dict[str, Any] = Field(..., description="Configuration for the trigger, e.g., cron string for schedule, topic name for pulsar.")

class Flow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the flow.")
    name: str = Field(..., description="Name of the integration flow.")
    description: Optional[str] = Field(default=None, description="Optional description for the flow.")
    trigger: FlowTrigger = Field(..., description="The event that triggers this flow.")
    steps: List[FlowStep] = Field(..., description="The sequence of steps to execute in the flow.")
    enabled: bool = Field(True, description="Whether the flow is currently active.") 