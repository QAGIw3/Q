import logging
import pulsar
import json
import threading
import time
from typing import Dict, Any, Optional, Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HumanFeedbackListener:
    """
    Listens for clarification requests from agentQ workers and forwards
    them to the appropriate user's WebSocket connection.
    """

    def __init__(self, service_url: str, topic: str):
        self._service_url = service_url
        self._topic = topic
        self._client: Optional[pulsar.Client] = None
        self._consumer: Optional[pulsar.Consumer] = None
        
        # This callback will be set by the WebSocket manager to forward messages
        self.forward_to_user_callback: Optional[Callable[[str, Dict], None]] = None
        
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the listener in a background thread."""
        if self._running:
            return
            
        self._client = pulsar.Client(self._service_url)
        self._consumer = self._client.subscribe(
            self._topic,
            subscription_name="h2m-human-feedback-sub",
            subscription_type=pulsar.SubscriptionType.Shared
        )
        
        self._running = True
        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info("HumanFeedbackListener started.")

    def stop(self):
        """Stops the listener."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._client:
            self._client.close()
        logger.info("HumanFeedbackListener stopped.")

    def _run_consumer(self):
        """The main loop for consuming feedback messages."""
        while self._running:
            try:
                msg = self._consumer.receive(timeout_millis=1000)
                message_data = json.loads(msg.data().decode('utf-8'))
                
                conversation_id = message_data.get("conversation_id")
                
                if self.forward_to_user_callback and conversation_id:
                    # Forward the message to the active WebSocket connection
                    self.forward_to_user_callback(conversation_id, message_data)
                
                self._consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in HumanFeedbackListener consumer loop: {e}", exc_info=True)
                time.sleep(5)

# Global instance
human_feedback_listener: Optional[HumanFeedbackListener] = None 