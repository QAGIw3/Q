import pulsar
from pulsar.schema import JsonSchema
import logging
import uuid
from typing import Optional
import json
from datetime import datetime, timezone

from shared.q_pulse_client.models import InferenceResponse
from app.core.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class H2MPulsarClient:
    """
    Manages Pulsar interactions for the H2M service.
    """
    def __init__(self):
        pulsar_config = get_config().pulsar
        self.client = pulsar.Client(pulsar_config.service_url)
        self.reply_topic_prefix = pulsar_config.topics.reply_prefix
        self.human_response_topic = pulsar_config.topics.human_response_topic
        self.human_feedback_topic = pulsar_config.topics.human_feedback_topic
        self._response_producer: Optional[pulsar.Producer] = None
        self._feedback_producer: Optional[pulsar.Producer] = None

    def start_producers(self):
        """Initializes all required producers."""
        if self._response_producer is None:
            self._response_producer = self.client.create_producer(self.human_response_topic)
            logger.info(f"Created producer for human responses on topic: {self.human_response_topic}")
        
        if self._feedback_producer is None:
            self._feedback_producer = self.client.create_producer(self.human_feedback_topic)
            logger.info(f"Created producer for human feedback on topic: {self.human_feedback_topic}")

    async def send_human_response(self, conversation_id: str, response_text: str):
        """Sends a human's response back to the agent."""
        if not self._response_producer:
            raise RuntimeError("Producers not started. Call start_producers() first.")
        
        message_payload = {
            "conversation_id": conversation_id,
            "response": response_text
        }
        self._response_producer.send(json.dumps(message_payload).encode('utf-8'))
        logger.info(f"Sent human response for conversation {conversation_id}")

    async def send_feedback(self, feedback_data: dict):
        """Sends feedback data to the feedback topic."""
        if not self._feedback_producer:
            raise RuntimeError("Producers not started. Call start_producers() first.")
        
        # Add a timestamp to the feedback data
        feedback_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        self._feedback_producer.send(json.dumps(feedback_data).encode('utf-8'))
        logger.info(f"Sent feedback for conversation {feedback_data.get('conversation_id')}")

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
        if self._response_producer:
            self._response_producer.close()
        if self._feedback_producer:
            self._feedback_producer.close()
        self.client.close()

# Add pulsar config to H2M config model
from app.core.config import AppConfig, BaseModel

class PulsarTopics(BaseModel):
    reply_prefix: str
    human_response_topic: str
    human_feedback_topic: str

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