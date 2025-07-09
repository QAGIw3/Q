from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field
from keycloak import KeycloakOpenID
import yaml
import uvicorn
import structlog

from shared.observability.logging_config import setup_logging
from shared.observability.metrics import setup_metrics

# --- Configuration & Logging ---
setup_logging()
logger = structlog.get_logger(__name__)

# --- Configuration ---
def load_config():
    with open("config/auth.yaml", 'r') as f:
        return yaml.safe_load(f)

config = load_config()
keycloak_config = config.get("keycloak", {})

keycloak_openid = KeycloakOpenID(
    server_url=keycloak_config.get("server_url"),
    client_id=keycloak_config.get("client_id"),
    realm_name=keycloak_config.get("realm_name"),
    client_secret_key=keycloak_config.get("client_secret")
)

# --- FastAPI App ---
app = FastAPI(
    title="AuthQ",
    description="Authentication and Authorization Service for the Q Platform.",
    version="0.1.0"
)

# --- Pydantic Models ---
class TokenRequest(BaseModel):
    username: str = Field(..., description="User's username")
    password: str = Field(..., description="User's password")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

# --- API Endpoints ---

@app.post("/token", response_model=TokenResponse, tags=["Authentication"])
async def login_for_access_token(form_data: TokenRequest):
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


@app.get("/health", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
