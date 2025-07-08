from fastapi import APIRouter, HTTPException, status, Depends
import logging

from shared.q_vectorstore_client.models import UpsertRequest
from app.core.milvus_handler import milvus_handler
from shared.q_auth_parser.parser import get_user_claims
from shared.q_auth_parser.models import UserClaims

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

AUTHORIZED_ROLES = {"admin", "service-account"}

@router.post("/upsert", status_code=status.HTTP_202_ACCEPTED)
async def upsert_vectors(
    request: UpsertRequest,
    claims: UserClaims = Depends(get_user_claims)
):
    """
    Accepts a batch of vectors and upserts them into the specified Milvus collection.
    Requires 'admin' or 'service-account' role.
    """
    # Simple role-based authorization
    user_roles = set(claims.realm_access.roles)
    if not AUTHORIZED_ROLES.intersection(user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have the required roles to perform this action."
        )

    try:
        logger.info(f"Received upsert request for collection '{request.collection_name}' with {len(request.vectors)} from user '{claims.sub}'.")
        result = milvus_handler.upsert(request.collection_name, request.vectors)
        return {
            "message": "Upsert request accepted and processed.",
            "insert_count": result['insert_count'],
            "primary_keys": result['primary_keys']
        }
    except ValueError as ve:
        logger.warning(f"Upsert failed due to invalid input: {ve}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"An unexpected error occurred during upsert: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while processing the upsert request.") 