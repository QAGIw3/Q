import httpx
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class KnowledgeGraphClient:
    """
    A client for interacting with the KnowledgeGraphQ service API.
    """

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url
        # In a real system, the token would be managed more securely
        self._token = token or os.getenv("KG_API_TOKEN", "dummy-token")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self._token}"}
        )

    async def execute_gremlin_query(self, query: str) -> Dict[str, Any]:
        """
        Executes a raw Gremlin query against the KnowledgeGraphQ API.
        """
        try:
            response = await self._client.post("/api/v1/query", json={"query": query})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error executing Gremlin query: {e.response.text}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while querying KnowledgeGraphQ: {e}", exc_info=True)
            raise

    async def ingest_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sends a list of ingestion operations to the KnowledgeGraphQ API.
        """
        try:
            response = await self._client.post("/api/v1/ingest", json={"operations": operations})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error ingesting data: {e.response.text}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while ingesting to KnowledgeGraphQ: {e}", exc_info=True)
            raise

    async def close(self):
        """Closes the async client."""
        await self._client.aclose()

# A default instance for convenience
KGQ_API_URL = os.getenv("KGQ_API_URL", "http://knowledgegraphq:8000")
kgq_client = KnowledgeGraphClient(base_url=KGQ_API_URL) 