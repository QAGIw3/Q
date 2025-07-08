import logging
from pyignite.client import Client
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

class ContextManager:
    """
    Manages the conversational memory for an agent instance in Ignite.
    """

    def __init__(self, ignite_addresses: List[str], agent_id: str):
        self.agent_id = agent_id
        self._client = Client()
        self._ignite_addresses = ignite_addresses
        self._cache = None
        logger.info(f"ContextManager initialized for agent {agent_id}")

    def connect(self):
        """Connects to Ignite and gets the agent context cache."""
        try:
            self._client.connect(self._ignite_addresses)
            # A single cache holds the context for all agents, keyed by agent_id
            self._cache = self._client.get_or_create_cache("agent_context")
            logger.info("Successfully connected to Ignite and got cache 'agent_context'.")
        except Exception as e:
            logger.error(f"Failed to connect ContextManager to Ignite: {e}", exc_info=True)
            raise

    def close(self):
        """Closes the Ignite connection."""
        if self._client.is_connected():
            self._client.close()

    def get_history(self, conversation_id: str) -> List[Dict]:
        """Retrieves the history for a specific conversation."""
        key = f"{self.agent_id}:{conversation_id}"
        history = self._cache.get(key)
        return history if history else []

    def append_to_history(self, conversation_id: str, new_messages: List[Dict]):
        """Appends new messages to a conversation's history."""
        key = f"{self.agent_id}:{conversation_id}"
        # Use a transactional get-and-put to handle concurrency safely
        
        # NOTE: pyignite's standard API is not truly transactional in a distributed
        # sense without using its specific transactional APIs. For this use case,
        # a simple get/put is sufficient as a single agent instance owns its context.
        
        current_history = self.get_history(conversation_id)
        current_history.extend(new_messages)
        self._cache.put(key, current_history)
        logger.info(f"Appended {len(new_messages)} messages to history for key '{key}'.") 