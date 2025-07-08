from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class InferenceRequest(BaseModel):
    """
    Defines the request sent to the QuantumPulse service.
    """
    prompt: str
    model: Optional[str] = None
    stream: bool = False
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class InferenceResponse(BaseModel):
    """
    Defines the response received from QuantumPulse when not streaming.
    NOTE: For H2M, we expect to primarily use a streaming response, which
    this client will handle as a generator, not a single object.
    """
    request_id: str
    response_id: str
    model: str
    text: str
    is_final: bool
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict) 