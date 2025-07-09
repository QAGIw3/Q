from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# --- Models for Asynchronous Inference Endpoint ---

class InferenceRequest(BaseModel):
    """
    Defines the request sent to the QuantumPulse async inference endpoint.
    """
    prompt: str
    model: Optional[str] = None
    stream: bool = False
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # The async endpoint needs a reply topic
    reply_to_topic: Optional[str] = None


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

# --- Models for Synchronous Chat Completion Endpoint ---

class QPChatMessage(BaseModel):
    role: str
    content: str

class QPChatRequest(BaseModel):
    model: str = Field(..., description="The model to use for the chat completion.")
    messages: List[QPChatMessage] = Field(..., description="A list of messages comprising the conversation so far.")
    temperature: float = 0.7
    max_tokens: int = 1500

class QPChatChoice(BaseModel):
    index: int
    message: QPChatMessage
    finish_reason: str

class QPChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class QPChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[QPChatChoice]
    usage: QPChatUsage 