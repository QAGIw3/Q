from fastapi import APIRouter, HTTPException, status, Depends
import logging

from shared.q_vectorstore_client.models import SearchRequest, SearchResponse
from app.core.milvus_handler import milvus_handler
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("", response_model=SearchResponse)
async def search_vectors(
    request: SearchRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Accepts a batch of search queries and performs similarity search on the specified Milvus collection.
    Requires any authenticated user.
    """
    try:
        logger.info(f"Received search request for collection '{request.collection_name}' with {len(request.queries)} queries from user '{user.username}'.")
        results = milvus_handler.search(request.collection_name, request.queries)
        return SearchResponse(results=results)
    except ValueError as ve:
        logger.warning(f"Search failed due to invalid input: {ve}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"An unexpected error occurred during search: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while processing the search request.") 