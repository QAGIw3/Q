# KnowledgeGraphQ/app/api/query.py
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
import logging

from ..core.gremlin_client import gremlin_client
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

logger = logging.getLogger(__name__)
router = APIRouter()

class GremlinQueryRequest(BaseModel):
    query: str

@router.post("")
async def execute_gremlin_query(
    request: GremlinQueryRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Executes a raw Gremlin query against the graph database.
    """
    try:
        logger.info(f"Executing Gremlin query from user '{user.username}': {request.query}")
        result = gremlin_client.execute_query(request.query)
        return {"result": result}
    except ConnectionError as e:
        logger.error(f"Query failed due to connection error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to graph database.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during query execution: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.") 