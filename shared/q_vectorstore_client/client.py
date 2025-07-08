import httpx
import logging
from typing import List

from .models import SearchRequest, SearchResponse, UpsertRequest, Query

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorStoreClient:
    """
    An asynchronous client for interacting with the VectorStoreQ service.
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        """
        Initializes the client.

        Args:
            base_url: The base URL of the VectorStoreQ service (e.g., http://localhost:8001).
            timeout: The timeout for HTTP requests in seconds.
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        logger.info(f"VectorStoreClient initialized for base URL: {base_url}")

    async def upsert(self, collection_name: str, vectors: List) -> None:
        """
        Upserts (inserts or updates) a batch of vectors into a collection.

        Args:
            collection_name: The name of the collection to upsert into.
            vectors: A list of Vector objects.
        """
        request_data = UpsertRequest(collection_name=collection_name, vectors=vectors)
        try:
            response = await self.client.post("/v1/ingest/upsert", json=request_data.dict())
            response.raise_for_status()
            logger.info(f"Successfully upserted {len(vectors)} vectors into '{collection_name}'.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Error upserting vectors: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"An error occurred while requesting {e.request.url!r}.")
            raise

    async def search(self, collection_name: str, queries: List[Query]) -> SearchResponse:
        """
        Performs a batch search for similar vectors in a collection.

        Args:
            collection_name: The name of the collection to search in.
            queries: A list of Query objects.

        Returns:
            A SearchResponse object containing the search results.
        """
        request_data = SearchRequest(collection_name=collection_name, queries=queries)
        try:
            response = await self.client.post("/v1/search", json=request_data.dict())
            response.raise_for_status()
            logger.info(f"Successfully performed search on '{collection_name}' with {len(queries)} queries.")
            return SearchResponse(**response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"Error searching vectors: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"An error occurred while requesting {e.request.url!r}.")
            raise

    async def close(self):
        """
        Closes the underlying HTTP client.
        Should be called when the client is no longer needed.
        """
        await self.client.aclose()
        logger.info("VectorStoreClient closed.") 