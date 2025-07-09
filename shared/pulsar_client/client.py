import pulsar
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

class SharedPulsarClient:
    """A shared, simplified Pulsar client for cross-service publishing."""
    
    def __init__(self, service_url: str):
        self._client: Optional[pulsar.Client] = None
        self._producers: Dict[str, pulsar.Producer] = {}
        self.service_url = service_url

    def _connect(self):
        if not self._client or self._client.is_closed():
            try:
                self._client = pulsar.Client(self.service_url)
                logger.info(f"SharedPulsarClient connected to {self.service_url}")
            except Exception as e:
                logger.error(f"Failed to connect SharedPulsarClient to {self.service_url}: {e}", exc_info=True)
                raise

    def get_producer(self, topic: str) -> pulsar.Producer:
        """Gets or creates a producer for a specific topic."""
        if topic not in self._producers:
            self._connect()
            try:
                self._producers[topic] = self._client.create_producer(topic)
            except Exception as e:
                logger.error(f"Failed to create producer for topic {topic}: {e}", exc_info=True)
                raise
        return self._producers[topic]

    def publish_message(self, topic: str, data: Dict[str, Any]):
        """Publishes a JSON-serialized message to a topic."""
        try:
            producer = self.get_producer(topic)
            producer.send_async(json.dumps(data).encode('utf-8'), callback=lambda res, msg_id: None)
        except Exception as e:
            logger.error(f"Failed to publish message to {topic}: {e}", exc_info=True)

    def publish_structured_event(self, event_type: str, source: str, payload: Dict[str, Any], topic: str = "persistent://public/default/platform-events"):
        """
        Constructs a standardized event and publishes it to a Pulsar topic.

        Args:
            event_type: A string identifying the type of event (e.g., "flow.triggered").
            source: The name of the service or component generating the event.
            payload: A dictionary containing the event's data.
            topic: The Pulsar topic to publish to.
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        }
        self.publish_message(topic, event)
        logger.info(f"Published structured event '{event_type}' from '{source}'.")

    def close(self):
        if self._client:
            self._client.close()
            logger.info("SharedPulsarClient connection closed.")

# Singleton instance
# Configuration can be overridden by environment variables or a config loader
PULSAR_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://pulsar:6650")
shared_pulsar_client = SharedPulsarClient(service_url=PULSAR_URL) 