import pulsar
import json
import logging
from typing import Dict, Any

from app.models.connector import Connector, ConnectorAction
from app.core.pulsar_client import pulsar_client

logger = logging.getLogger(__name__)

class PulsarPublisher(Connector):
    """
    A connector to publish messages to an Apache Pulsar topic.
    """
    
    @property
    def connector_id(self) -> str:
        return "pulsar-publish"

    async def execute(self, action: ConnectorAction, configuration: Dict[str, Any], data_context: Dict[str, Any]) -> Dict[str, Any]:
        topic = configuration.get("topic")
        message_payload = configuration.get("message")

        if not topic or not message_payload:
            raise ValueError("Pulsar publisher requires 'topic' and 'message' in configuration.")

        try:
            producer = pulsar_client.create_producer(topic)
            
            # The message payload from the previous step might be a complex object (e.g., a list of dicts).
            # We serialize it to a JSON string before sending.
            message_bytes = json.dumps(message_payload).encode('utf-8')
            
            producer.send(message_bytes)
            logger.info(f"Successfully published message to Pulsar topic: {topic}")
            
            return {"status": "published", "topic": topic}
        except Exception as e:
            logger.error(f"Failed to publish to Pulsar topic {topic}: {e}", exc_info=True)
            raise


# Instantiate the connector
pulsar_publisher_connector = PulsarPublisher()
