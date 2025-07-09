from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = Field(..., description="The model to use for the chat completion.")
    messages: List[ChatMessage] = Field(..., description="A list of messages comprising the conversation so far.")
    temperature: float = 0.7
    max_tokens: int = 1500
    stream: bool = False # Streaming is not yet supported on this endpoint

class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str

class ChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: ChatUsage 