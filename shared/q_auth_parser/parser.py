from fastapi import Header, HTTPException, status, Query as FastApiQuery, Depends
from fastapi.security import OAuth2PasswordBearer
import json
import base64
import logging
from typing import Optional
import yaml
from jose import JWTError, jwt
from keycloak import KeycloakOpenID

from .models import UserClaims

# Configure logging
logger = logging.getLogger(__name__)

# --- Keycloak Configuration ---

def load_keycloak_config():
    # This path is relative to the service root, not this file.
    # TODO: Make this path configurable via environment variable.
    with open("../AuthQ/config/auth.yaml", 'r') as f:
        return yaml.safe_load(f)["keycloak"]

keycloak_config = load_keycloak_config()

keycloak_openid = KeycloakOpenID(
    server_url=keycloak_config["server_url"],
    client_id=keycloak_config["client_id"],
    realm_name=keycloak_config["realm_name"],
    client_secret_key=keycloak_config["client_secret"]
)

# Fetch the public key from Keycloak's certs endpoint
keycloak_public_key = "-----BEGIN PUBLIC KEY-----\n" + keycloak_openid.public_key() + "\n-----END PUBLIC KEY-----"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserClaims:
    """
    FastAPI dependency to decode and validate a JWT token from the Authorization header.
    Returns the user claims upon successful validation.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the token using Keycloak's public key
        payload = jwt.decode(
            token,
            keycloak_public_key,
            algorithms=["RS256"],
            audience=keycloak_config.get("client_id"), # or another client like 'account'
            options={"verify_signature": True, "verify_aud": True, "exp": True}
        )
        
        # Map Keycloak claims to our UserClaims model
        # Note: You may need to adjust these field names based on your Keycloak token configuration
        user_claims = UserClaims(
            user_id=payload.get("sub"),
            username=payload.get("preferred_username"),
            email=payload.get("email"),
            roles=payload.get("realm_access", {}).get("roles", []),
        )
        return user_claims
    except JWTError as e:
        logger.error(f"JWT Error: {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        logger.error(f"User claims validation failed: {e}", exc_info=True)
        raise credentials_exception


async def get_current_user_ws(token: Optional[str] = FastApiQuery(None)) -> UserClaims:
    """
    FastAPI dependency for WebSocket connections.
    Extracts a JWT token from a query parameter and validates it.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing from query parameters",
        )
    # Re-use the same logic as the header-based dependency
    return await get_current_user(token)


# The default header Istio uses to pass JWT claims after validation.
# This can be configured in the Istio `RequestAuthentication` resource.
CLAIMS_HEADER = "X-User-Claims"

def _parse_and_validate_claims(claims_data: str) -> UserClaims:
    """Internal helper to decode and validate claims."""
    if not claims_data:
        logger.warning(f"Authentication data is missing from the request.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User claims not found. Is the request coming through the gateway?",
        )

    try:
        # The data is expected to be a base64 encoded JSON string
        decoded_claims = base64.b64decode(claims_data).decode("utf-8")
        claims_json = json.loads(decoded_claims)
        
        # Validate the JSON data against our Pydantic model
        user_claims = UserClaims(**claims_json)
        return user_claims

    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to decode or parse claims: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid claims format.",
        )
    except Exception as e:
        # This will catch Pydantic's ValidationError
        logger.error(f"Failed to validate claims model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid claims data: {e}",
        )

def get_user_claims(claims_header: Optional[str] = Header(None, alias=CLAIMS_HEADER)) -> UserClaims:
    """
    A FastAPI dependency for standard HTTP requests. It extracts claims from a header.
    """
    return _parse_and_validate_claims(claims_header)


def get_user_claims_ws(claims: Optional[str] = FastApiQuery(None)) -> UserClaims:
    """
    A FastAPI dependency for WebSocket connections. It extracts claims from a query parameter.
    
    Example WS URL: ws://localhost:8002/chat/ws?claims=<base64-encoded-claims>
    """
    return _parse_and_validate_claims(claims) 