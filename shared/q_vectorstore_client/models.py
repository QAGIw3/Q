from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Vector(BaseModel):
    """
    Represents a single vector and its associated metadata.
    """
    id: str
    values: List[float]
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UpsertRequest(BaseModel):
    """
    A request to insert or update vectors in a collection.
    """
    collection_name: str
    vectors: List[Vector]

class Query(BaseModel):
    """
    Represents a single query vector for a search operation.
    """
    values: List[float]
    top_k: int = 10
    filter: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    """
    A request to search for similar vectors in a collection.
    """
    collection_name: str
    queries: List[Query]

class SearchHit(BaseModel):
    """
    Represents a single search result (a "hit").
    """
    id: str
    score: float
    metadata: Optional[Dict[str, Any]] = None

class QueryResult(BaseModel):
    """
    Contains the list of hits for a single query.
    """
    hits: List[SearchHit]

class SearchResponse(BaseModel):
    """
    The response from a search request, containing results for each query.
    """
    results: List[QueryResult] 