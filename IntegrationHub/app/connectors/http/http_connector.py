import logging
import httpx
from typing import Dict, Any, Optional

from app.models.connector import BaseConnector, ConnectorAction
from app.core.vault_client import vault_client

logger = logging.getLogger(__name__)

class HttpConnector(BaseConnector):
    """
    A generic connector for making HTTP requests to other services.
    """

    @property
    def connector_id(self) -> str:
        return "http"

    async def execute(self, action: ConnectorAction, configuration: Dict[str, Any], data_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = configuration.get("method", "POST").upper()
        url = configuration.get("url")
        headers = configuration.get("headers", {})
        params = configuration.get("params")
        json_payload = configuration.get("json")

        if not url:
            raise ValueError("HTTP Connector requires 'url' in configuration.")

        # If a credential is provided, fetch it and add it as a Bearer token.
        if action.credential_id:
            credential = await vault_client.get_credential(action.credential_id)
            # Assuming the secret is stored with a key like 'token' or 'api_key'
            token = credential.secrets.get("token") or credential.secrets.get("api_key")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Executing HTTP {method} request to {url}")
                
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_payload,
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                # The response body will be passed to the next step in the flow
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP request failed: {e.response.status_code} - {e.response.text}")
                # Re-raise to fail the flow step
                raise e
            except Exception as e:
                logger.error(f"An unexpected error occurred in HttpConnector: {e}", exc_info=True)
                raise e

# Instantiate a single instance
http_connector = HttpConnector()
