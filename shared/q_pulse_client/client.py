import httpx
import logging
import asyncio

from .models import InferenceRequest, QPChatRequest, QPChatResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuantumPulseClient:
    """
    An asynchronous client for interacting with the QuantumPulse service.
    """

    def __init__(self, base_url: str, timeout: float = 60.0):
        """
        Initializes the client.

        Args:
            base_url: The base URL of the QuantumPulse service (e.g., http://localhost:8000).
            timeout: The timeout for HTTP requests.
        """
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self.timeout = timeout
        logger.info(f"QuantumPulseClient initialized for base URL: {base_url}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Initializes the async client on first use."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def submit_inference(self, request: InferenceRequest) -> str:
        """
        Submits an inference request to the QuantumPulse service.
        This is a "fire-and-forget" operation. The response is handled
        asynchronously by other services (like a WebSocket handler).

        Args:
            request: An InferenceRequest object.

        Returns:
            The request_id for tracking.
        """
        client = await self._get_client()
        try:
            response = await client.post("/v1/inference", json=request.dict())
            response.raise_for_status()
            response_data = response.json()
            request_id = response_data.get("request_id")
            logger.info(f"Successfully submitted inference request {request_id} to QuantumPulse.")
            return request_id
        except httpx.HTTPStatusError as e:
            logger.error(f"Error submitting inference request: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"An error occurred while requesting {e.request.url!r}.")
            raise

    async def get_chat_completion(self, request: QPChatRequest) -> QPChatResponse:
        """
        Gets a synchronous chat completion from the QuantumPulse service.

        Args:
            request: A QPChatRequest object.

        Returns:
            A QPChatResponse object containing the completion.
        """
        client = await self._get_client()
        try:
            # Note the different endpoint path
            response = await client.post("/v1/chat/completions", json=request.dict())
            response.raise_for_status()
            response_data = response.json()
            return QPChatResponse(**response_data)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error getting chat completion: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"An error occurred while requesting chat completion: {e.request.url!r}.")
            raise

    async def close(self):
        """
        Closes the underlying HTTP client.
        """
        if self._client:
            await self._client.aclose()
            logger.info("QuantumPulseClient closed.") 