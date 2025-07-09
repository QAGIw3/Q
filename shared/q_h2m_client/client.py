# shared/q_h2m_client/client.py
import httpx
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class H2MClient:
    """
    A client for interacting with the H2M service API, specifically the model registry.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=self.base_url)

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Fetches all model entries from the H2M model registry.
        """
        try:
            response = await self._client.get("/api/v1/registry/")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to H2M service: {e}", exc_info=True)
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"Error fetching models from registry: {e.response.text}", exc_info=True)
            return []

    async def activate_model(self, model_name: str) -> Dict[str, Any]:
        """
        Calls the H2M service to activate a specific model.
        """
        try:
            response = await self._client.post(f"/api/v1/registry/{model_name}/activate")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to H2M service to activate model: {e}", exc_info=True)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Error activating model '{model_name}': {e.response.text}", exc_info=True)
            raise

    async def get_active_models(self, base_model: str) -> List[Dict[str, Any]]:
        """
        Fetches all active models for a specific base model type.
        """
        all_models = await self.list_models()
        active_models = [
            m for m in all_models 
            if m.get("is_active") and m.get("metadata", {}).get("base_model") == base_model
        ]
        return active_models

    async def close(self):
        await self._client.aclose()

# Default instance
H2M_API_URL = os.getenv("H2M_API_URL", "http://h2m-service:80")
h2m_client = H2MClient(base_url=H2M_API_URL) 