from fastapi import Header, HTTPException, status
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

def get_user_claims(claims_header: Optional[str] = Header(None, alias=CLAIMS_HEADER)) -> UserClaims:
    """
    A FastAPI dependency that extracts, decodes, and validates user claims
    from a request header populated by the Istio gateway.

    The Istio gateway is responsible for authenticating the JWT. This function
    only trusts the header and parses the claims payload.

    Args:
        claims_header: The raw, base64-encoded JSON string from the header.

    Returns:
        A validated UserClaims object.

    Raises:
        HTTPException: If the header is missing or the claims are invalid.
    """
    if not claims_header:
        logger.warning(f"Authentication header '{CLAIMS_HEADER}' is missing from the request.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User claims not found in request headers. Is the request coming through the gateway?",
        )

    try:
        # The header is expected to be a base64 encoded JSON string
        decoded_claims = base64.b64decode(claims_header).decode("utf-8")
        claims_json = json.loads(decoded_claims)
        
        # Validate the JSON data against our Pydantic model
        user_claims = UserClaims(**claims_json)
        return user_claims

    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to decode or parse claims from header: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid claims format in header.",
        )
    except Exception as e:
        # This will catch Pydantic's ValidationError
        logger.error(f"Failed to validate claims model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid claims data: {e}",
        ) 