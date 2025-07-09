import logging
import pulsar
import fastavro
import io
import threading
from typing import Optional
import asyncio

from app.core.connection_manager import manager
from app.core.config import get_config

logger = logging.getLogger(__name__)

# Avro schema for the thought messages, must match agentQ's schema
THOUGHT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ThoughtMessage",
    "fields": [
        {"name": "conversation_id", "type": "string"},
        {"name": "thought", "type": "string"},
        {"name": "timestamp", "type": "long"},
    ]
})

class ThoughtListener:
    """
    A background service that listens for agent thoughts and forwards them
    to the appropriate user via their WebSocket connection.
    """
    def __init__(self):
        pulsar_config = get_config().pulsar
        self.service_url = pulsar_config.service_url
        self.topic = pulsar_config.topics.agent_thoughts_topic
        self.client: Optional[pulsar.Client] = None
        self.consumer: Optional[pulsar.Consumer] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the listener in a background thread."""
        if self._running:
            return
        
        self.client = pulsar.Client(self.service_url)
        self.consumer = self.client.subscribe(
            self.topic,
            subscription_name="h2m-thought-listener-sub",
            subscription_type=pulsar.SubscriptionType.Shared
        )
        self._running = True
        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info(f"ThoughtListener started and subscribed to topic: {self.topic}")

    def stop(self):
        """Stops the listener."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self.consumer:
            self.consumer.close()
        if self.client:
            self.client.close()
        logger.info("ThoughtListener stopped.")

    def _run_consumer(self):
        """The main loop for consuming thought messages."""
        while self._running:
            try:
                msg = self.consumer.receive()
                bytes_reader = io.BytesIO(msg.data())
                thought_data = next(fastavro.reader(bytes_reader, THOUGHT_SCHEMA), None)
                
                if thought_data:
                    conversation_id = thought_data.get("conversation_id")
                    thought_text = thought_data.get("thought")
                    
                    # Forward the thought to the user's WebSocket
                    asyncio.run(manager.send_to_conversation(
                        conversation_id, 
                        {"type": "thought", "text": thought_text}
                    ))
                
                self.consumer.acknowledge(msg)
            except Exception as e:
                logger.error(f"Error in ThoughtListener consumer loop: {e}", exc_info=True)

# Global instance
thought_listener = ThoughtListener() 