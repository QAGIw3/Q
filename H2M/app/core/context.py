import logging
from typing import List, Dict, Optional
import uuid

from app.services.ignite_client import ignite_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContextManager:
    """
    Manages the context and history of conversations, scoped by user.
    """

    def _get_cache_key(self, user_id: str, conversation_id: str) -> str:
        """Creates a composite key for the cache."""
        return f"{user_id}:{conversation_id}"

    async def get_or_create_conversation_history(self, user_id: str, conversation_id: Optional[str]) -> (str, List[Dict]):
        """
        Retrieves the history for a user's conversation, or creates a new one.
        """
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logger.info(f"No conversation_id provided for user {user_id}. Created new one: {conversation_id}")
            return conversation_id, []

        cache_key = self._get_cache_key(user_id, conversation_id)
        history = await ignite_client.get_history(cache_key)
        
        if history is None:
            logger.warning(f"No history found for key {cache_key}. Starting new history.")
            return conversation_id, []
        
        return conversation_id, history

    async def add_message_to_history(self, user_id: str, conversation_id: str, user_message: str, ai_message: str):
        """
        Adds a new turn to a user's conversation history.
        """
        _id, history = await self.get_or_create_conversation_history(user_id, conversation_id)

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": ai_message})

        cache_key = self._get_cache_key(user_id, conversation_id)
        await ignite_client.save_history(cache_key, history)
        logger.info(f"Appended messages to history for cache key {cache_key}.")

# Global instance for the application
context_manager = ContextManager() 