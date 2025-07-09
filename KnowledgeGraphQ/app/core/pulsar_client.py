import pulsar
import logging

logger = logging.getLogger(__name__)

class PulsarClient:
    def __init__(self, service_url: str):
        self.service_url = service_url
        self.client = None

    def connect(self):
        try:
            self.client = pulsar.Client(self.service_url)
            logger.info(f"Successfully connected to Pulsar at {self.service_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Pulsar: {e}", exc_info=True)
            raise

    def subscribe(self, topic: str, subscription_name: str, message_listener):
        if not self.client:
            self.connect()
        
        try:
            consumer = self.client.subscribe(
                topic=topic,
                subscription_name=subscription_name,
                listener=message_listener
            )
            logger.info(f"Subscribed to topic '{topic}' with subscription '{subscription_name}'")
            return consumer
        except Exception as e:
            logger.error(f"Failed to subscribe to topic {topic}: {e}", exc_info=True)
            raise

    def close(self):
        if self.client:
            self.client.close()
            logger.info("Pulsar client connection closed.")

# TODO: Load from config
pulsar_client = PulsarClient("pulsar://pulsar:6650") 