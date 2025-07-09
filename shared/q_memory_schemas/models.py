from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone

class Memory(BaseModel):
    """
    A structured representation of an agent's memory from a single conversation or task.
    """
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_id: str
    conversation_id: str
    
    # Key extracted information
    summary: str = Field(..., description="A concise, one-paragraph summary of the key facts, findings, and conclusions.")
    entities: List[str] = Field(default_factory=list, description="A list of key entities involved (e.g., service names, technologies, people).")
    key_relationships: Dict[str, List[str]] = Field(default_factory=dict, description="A dictionary describing how entities are related (e.g., {'service:billing': ['uses:database', 'calls:auth_api']}).")
    outcome: str = Field(..., description="The final outcome of the task (e.g., 'SUCCESSFULLY_RESOLVED', 'FAILED_NEEDS_INFO', 'NO_ACTION_NEEDED').")
    
    # The original data for context
    full_prompt: str
    final_answer: str

class MemorySaveRequest(BaseModel):
    """
    The request payload sent to the save_memory tool.
    """
    memory: Memory 