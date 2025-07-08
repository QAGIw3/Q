import logging
from pyignite.client import Client
from pyignite.exceptions import CacheError
from typing import List, Dict, Optional

from app.core.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IgniteClient:
    """
    Handles connections and operations with an Apache Ignite cluster.
    """

    def __init__(self):
        ignite_config = get_config().ignite
        self.client = Client()
        self.addresses = ignite_config.addresses
        self.cache_name = ignite_config.cache_name
        self._cache = None

    async def connect(self):
        """

        Establishes a connection to the Ignite cluster.
        Note: The pyignite library is synchronous, so we wrap in async methods.
        """
        try:
            self.client.connect(self.addresses)
            self._cache = self.client.get_or_create_cache(self.cache_name)
            logger.info(f"Connected to Ignite and got cache '{self.cache_name}'.")
        except Exception as e:
            logger.error(f"Failed to connect to Ignite: {e}", exc_info=True)
            raise

    async def disconnect(self):
        """
        Disconnects from the Ignite cluster.
        """
        if self.client.is_connected():
            self.client.close()
            logger.info("Disconnected from Ignite.")

    async def get_history(self, conversation_id: str) -> Optional[List[Dict]]:
        """
        Retrieves the conversation history for a given ID.

        Args:
            conversation_id: The unique ID of the conversation.

        Returns:
            A list of message dictionaries, or None if not found.
        """
        try:
            history = self._cache.get(conversation_id)
            if history:
                logger.info(f"Retrieved history for conversation_id: {conversation_id}")
                return history
            return None
        except CacheError as e:
            logger.error(f"Error retrieving history for {conversation_id}: {e}", exc_info=True)
            return None

    async def save_history(self, conversation_id: str, history: List[Dict]) -> None:
        """
        Saves or updates the conversation history for a given ID.

        Args:
            conversation_id: The unique ID of the conversation.
            history: The full list of message dictionaries to save.
        """
        try:
            self._cache.put(conversation_id, history)
            logger.info(f"Saved history for conversation_id: {conversation_id}")
        except CacheError as e:
            logger.error(f"Error saving history for {conversation_id}: {e}", exc_info=True)
            raise

# Global instance to be used by the application
ignite_client = IgniteClient() 