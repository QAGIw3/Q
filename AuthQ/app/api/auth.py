# AuthQ/app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from keycloak import KeycloakOpenID
from typing import Dict, Any

from app.dependencies import get_keycloak_openid, get_current_user

router = APIRouter()

class TokenRequest(BaseModel):
    username: str = Field(..., description="User's username")
    password: str = Field(..., description="User's password")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: TokenRequest,
    keycloak_openid: KeycloakOpenID = Depends(get_keycloak_openid)
):
    """
    Authenticate user and return a JWT access token.
    """
    try:
        token = keycloak_openid.token(
            username=form_data.username,
            password=form_data.password
        )
        return {"access_token": token["access_token"], "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/introspect", response_model=Dict[str, Any])
async def introspect_token(
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Validates a token and returns its claims.
    This is a protected endpoint that services can call to validate a user token.
    """
    return user["claims"] 