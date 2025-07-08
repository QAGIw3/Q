import uuid
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class CredentialBase(BaseModel):
    name: str = Field(..., description="A unique, human-readable name for the credential.")
    type: str = Field(..., description="The type of the credential, e.g., 'zulip_api_key'.")
    description: Optional[str] = Field(default=None, description="An optional description for the credential.")

class CredentialCreate(CredentialBase):
    secrets: Dict[str, Any] = Field(..., description="The secret data for the credential, e.g., {'api_key': '...', 'email': '...'}.")

class Credential(CredentialBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the credential.")
    
    class Config:
        orm_mode = True 