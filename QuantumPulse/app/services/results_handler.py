import pulsar
from pulsar.schema import JsonSchema
import logging
import time
from typing import Optional

from app.models.inference import InferenceResponse
from app.core.config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResultsHandler:
    """
    Consumes inference results from Pulsar and handles them.
    
    In a real system, this service would be responsible for:
    - Looking up the original client connection details (e.g., from a cache like Ignite).
    - Pushing the result back to the client via WebSocket, SSE, or a webhook.
    - Storing the final result in a database.
    """

    def __init__(self):
        self.config = config
        self._client: Optional[pulsar.Client] = None
        self._consumer: Optional[pulsar.Consumer] = None

    def connect(self):
        """Connects to Pulsar and sets up the consumer."""
        pulsar_conf = self.config.pulsar
        self._client = pulsar.Client(pulsar_conf.service_url)
        
        results_topic = pulsar_conf.topics.results
        self._consumer = self._client.subscribe(
            results_topic,
            subscription_name="results-handler-sub",
            schema=JsonSchema(InferenceResponse)
        )
        logger.info(f"Subscribed to results topic: {results_topic}")

    def run(self):
        """The main loop for the results handler."""
        self.connect()
        logger.info("Results handler started. Waiting for messages...")

        while True:
            try:
                msg = self._consumer.receive()
                response = msg.value()
                
                try:
                    logger.info(
                        f"Received result for request {response.request_id}. "
                        f"Final: {response.is_final}. Text: '{response.text[:100]}...'"
                    )
                    
                    # Placeholder for actual result delivery logic
                    self.deliver_result(response)

                    self._consumer.acknowledge(msg)
                except Exception as e:
                    self._consumer.negative_acknowledge(msg)
                    logger.error(f"Failed to handle result for request {response.request_id}: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"An error occurred in the results handler loop: {e}", exc_info=True)
                time.sleep(5)

    def deliver_result(self, response: InferenceResponse):
        """
        A placeholder for the logic to deliver the result to the original client.
        """
        logger.info(f"Delivering result for request {response.request_id}...")
        # In a real implementation, this would involve a lookup and a push.
        time.sleep(0.1) # Simulate work
        logger.info("Delivery placeholder finished.")

    def close(self):
        """Cleans up resources."""
        if self._consumer:
            self._consumer.close()
        if self._client:
            self._client.close()
        logger.info("Results handler resources cleaned up.")


if __name__ == "__main__":
    handler = ResultsHandler()
    try:
        handler.run()
    except KeyboardInterrupt:
        handler.close() 