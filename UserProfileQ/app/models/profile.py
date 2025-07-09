# UserProfileQ/app/models/profile.py
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model
from typing import Optional, Dict

class ProfileModel(Model):
    __table_name__ = 'user_profiles'
    user_id = columns.UUID(primary_key=True, default=uuid.uuid4)
    username = columns.Text(required=True, index=True)
    email = columns.Text(required=True)
    full_name = columns.Text()
    preferences = columns.Map(columns.Text, columns.Text)
    created_at = columns.DateTime(default=datetime.utcnow)
    updated_at = columns.DateTime(default=datetime.utcnow)

    def to_dict(self):
        return {
            "user_id": str(self.user_id),
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "preferences": self.preferences,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class ProfileCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, str]] = {}

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, str]] = None

class ProfileResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, str]] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 