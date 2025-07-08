from fastapi import Header, HTTPException, status, Query as FastApiQuery
import json
import base64
import logging
from typing import Optional

from .models import UserClaims

# Configure logging
logger = logging.getLogger(__name__)

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