import httpx
import logging

from .models import InferenceRequest

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
        # The QuantumPulse service uses a fire-and-forget mechanism, so the client
        # doesn't need to handle long-lived connections for responses.
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        logger.info(f"QuantumPulseClient initialized for base URL: {base_url}")

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
        try:
            response = await self.client.post("/api/v1/inference", json=request.dict())
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

    async def close(self):
        """
        Closes the underlying HTTP client.
        """
        await self.client.aclose()
        logger.info("QuantumPulseClient closed.") 