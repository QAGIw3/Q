# AuthQ/app/models/user.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

class UserCreate(BaseModel):
    """
    Request model for creating a new user.
    """
    username: str = Field(..., description="The desired username.")
    email: EmailStr = Field(..., description="The user's email address.")
    password: str = Field(..., description="The user's password.")
    first_name: Optional[str] = Field(None, description="User's first name.")
    last_name: Optional[str] = Field(None, description="User's last name.")

class User(BaseModel):
    """
    Represents a user in the system.
    """
    id: str = Field(..., description="The unique user ID from Keycloak.")
    username: str
    email: EmailStr
    first_name: Optional[str]
    last_name: Optional[str]
    enabled: bool
    email_verified: bool
    created_timestamp: int
    roles: List[str] = [] 