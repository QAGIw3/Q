import pulsar
from pulsar.schema import JsonSchema
import logging
import uuid
from typing import Optional

from shared.q_pulse_client.models import InferenceResponse
from app.core.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class H2MPulsarClient:
    """
    Manages Pulsar interactions for the H2M service, specifically for
    handling real-time replies to inference requests.
    """
    def __init__(self):
        pulsar_config = get_config().pulsar
        self.client = pulsar.Client(pulsar_config.service_url)
        self.reply_topic_prefix = pulsar_config.topics.get("reply_prefix", "persistent://public/default/h2m-replies-")

    async def create_consumer_for_reply(self) -> (str, pulsar.Consumer):
        """
        Creates a temporary, exclusive subscription to a unique reply topic.
        Does not wait for a message.

        Returns:
            A tuple containing the reply topic name and the consumer instance.
        """
        reply_topic = f"{self.reply_topic_prefix}{uuid.uuid4()}"
        consumer = self.client.subscribe(
            reply_topic,
            subscription_name=f"h2m-reply-sub-{uuid.uuid4()}",
            schema=JsonSchema(InferenceResponse),
            subscription_type=pulsar.SubscriptionType.Exclusive,
        )
        logger.info(f"Created temporary consumer on topic: {reply_topic}")
        return reply_topic, consumer

    async def await_response(self, consumer: pulsar.Consumer) -> pulsar.Message:
        """
        Waits for a single message on a given consumer.

        Args:
            consumer: The consumer to listen on.

        Returns:
            The received message.
        """
        logger.info(f"Awaiting response on topic: {consumer.topic()}")
        # This is a synchronous call, so it will block in an executor.
        # A fully async app might use consumer.receive_async()
        msg = consumer.receive(timeout_millis=30000) # 30-second timeout
        logger.info(f"Received response on topic {consumer.topic()}")
        return msg
    
    def close(self):
        self.client.close()

# Add pulsar config to H2M config model
from app.core.config import AppConfig, BaseModel

class PulsarTopics(BaseModel):
    reply_prefix: str

class PulsarConfig(BaseModel):
    service_url: str
    topics: PulsarTopics

# Add it to the main AppConfig
# This is a bit of a hacky way to extend the config.
# A better way would be to have a shared config model.
if not hasattr(AppConfig.__fields__, 'pulsar'):
    AppConfig.add_fields(pulsar=PulsarConfig)

# Global instance
h2m_pulsar_client = H2MPulsarClient() 