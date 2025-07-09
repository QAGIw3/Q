from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal

from ..core.gremlin_client import gremlin_client
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Pydantic Models for Ingestion ---

class UpsertVertex(BaseModel):
    operation: Literal["upsert_vertex"]
    label: str = Field(..., description="The label of the vertex (e.g., 'Service', 'Flow', 'PullRequest').")
    id_key: str = Field(default="uid", description="The property key to use as a unique identifier.")
    properties: Dict[str, Any] = Field(..., description="A dictionary of properties for the vertex. Must include the id_key.")

class UpsertEdge(BaseModel):
    operation: Literal["upsert_edge"]
    label: str = Field(..., description="The label for the edge (e.g., 'TRIGGERS', 'CONTAINS', 'SUBMITTED_BY').")
    from_vertex_id: str = Field(..., description="The unique ID of the source vertex.")
    to_vertex_id: str = Field(..., description="The unique ID of the destination vertex.")
    from_vertex_label: str = Field(..., description="The label of the source vertex.")
    to_vertex_label: str = Field(..., description="The label of the destination vertex.")
    id_key: str = Field(default="uid", description="The property key used to look up the vertices.")

class IngestRequest(BaseModel):
    operations: List[UpsertVertex | UpsertEdge]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_updates(
    request: IngestRequest,
    # For service-to-service communication, we would likely use a different auth method.
    # For now, we'll keep user auth for simplicity.
    user: UserClaims = Depends(get_current_user) 
):
    """
    Accepts a list of operations to ingest into the knowledge graph.
    """
    logger.info(f"Received ingestion request with {len(request.operations)} operations from user '{user.username}'.")
    try:
        for op in request.operations:
            if op.operation == "upsert_vertex":
                gremlin_client.upsert_vertex(
                    label=op.label,
                    properties=op.properties,
                    id_key=op.id_key
                )
            elif op.operation == "upsert_edge":
                gremlin_client.upsert_edge(
                    label=op.label,
                    from_vertex_id=op.from_vertex_id,
                    to_vertex_id=op.to_vertex_id,
                    from_vertex_label=op.from_vertex_label,
                    to_vertex_label=op.to_vertex_label,
                    id_key=op.id_key
                )
    except ValueError as e:
        logger.error(f"Validation error during ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        logger.error(f"Could not connect to graph database during ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to graph database.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")
        
    return {"status": "Ingestion request accepted."} 