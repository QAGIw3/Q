from pydantic import BaseModel, Field
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
import logging

from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

class FieldSchema(BaseModel):
    """Defines the schema for a single field in a Milvus collection."""
    name: str
    dtype: str # e.g., "Int64", "VarChar", "FloatVector"
    is_primary: bool = False
    max_length: int | None = None # For VarChar
    dim: int | None = None # For FloatVector

class CollectionSchema(BaseModel):
    """Defines the schema for a new Milvus collection."""
    collection_name: str
    description: str = ""
    fields: List[FieldSchema]
    enable_dynamic_field: bool = True

class IndexParams(BaseModel):
    """Defines the parameters for creating an index on a vector field."""
    field_name: str
    index_type: str = "HNSW"
    metric_type: str = "COSINE"
    params: Dict[str, Any] = Field(default_factory=lambda: {"M": 16, "efConstruction": 256})

class CreateCollectionRequest(BaseModel):
    """The complete request to create a new collection and its index."""
    schema: CollectionSchema
    index: IndexParams

# --- API Endpoint ---

from app.core.milvus_handler import milvus_handler

logger = logging.getLogger(__name__)
router = APIRouter()

AUTHORIZED_ROLES = {"admin", "service-account"}

@router.post("/create-collection", status_code=status.HTTP_201_CREATED)
async def create_collection(
    request: CreateCollectionRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Creates a new collection in Milvus with a specified schema and index.
    This operation is idempotent; if the collection already exists, it will do nothing.
    Requires 'admin' or 'service-account' role.
    """
    user_roles = set(user.roles)
    if not AUTHORIZED_ROLES.intersection(user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have the required roles to perform this action."
        )

    try:
        logger.info(f"User '{user.username}' requested to create collection: {request.schema.collection_name}")
        result = milvus_handler.create_collection_with_index(
            schema_def=request.schema,
            index_params=request.index
        )
        if result["created"]:
            return {"message": "Collection created successfully."}
        else:
            return {"message": f"Collection '{request.schema.collection_name}' already exists."}
    except Exception as e:
        logger.error(f"Failed to create collection '{request.schema.collection_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred: {e}"
        ) 