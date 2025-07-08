from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid

class InferenceRequest(BaseModel):
    """
    Represents a request for inference from a client.
    """
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str
    model: Optional[str] = None  # Specific model to target, optional
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False  # If true, results are streamed back
    conversation_id: Optional[str] = None # To maintain context
    metadata: Dict[str, Any] = Field(default_factory=dict)

class InferenceResponse(BaseModel):
    """
    Represents a single response chunk or the final response from the model.
    """
    request_id: str
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model: str
    text: str
    is_final: bool = True
    conversation_id: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PreprocessedInferenceRequest(InferenceRequest):
    """
    Represents a request after initial preprocessing (e.g., cleaning, tokenizing).
    This is an internal representation.
    """
    tokens: List[int] = Field(default_factory=list)

class RoutedInferenceRequest(PreprocessedInferenceRequest):
    """
    Represents a request that has been routed to a specific model shard.
    This is an internal representation.
    """
    target_shard: str 