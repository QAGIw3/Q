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
        self._context_cache = None
        self._reflexion_cache = None
        logger.info(f"ContextManager initialized for agent {agent_id}")

    def connect(self):
        """Connects to Ignite and gets the required caches."""
        try:
            self._client.connect(self._ignite_addresses)
            # Cache for conversation history and scratchpads
            self._context_cache = self._client.get_or_create_cache("agent_context")
            # Cache for storing generated reflexions
            self._reflexion_cache = self._client.get_or_create_cache("agent_reflexions")
            logger.info("Successfully connected to Ignite and got caches 'agent_context' and 'agent_reflexions'.")
        except Exception as e:
            logger.error(f"Failed to connect ContextManager to Ignite: {e}", exc_info=True)
            raise

    def close(self):
        """Closes the Ignite connection."""
        if self._client.is_connected():
            self._client.close()

    def get_history(self, conversation_id: str) -> List[Dict]:
        """
        Retrieves the history for a specific conversation.
        Handles both old (list) and new (dict) storage formats.
        """
        key = f"{self.agent_id}:{conversation_id}"
        stored_data = self._context_cache.get(key)
        
        if not stored_data:
            return []
        
        # Check if it's the new format (a dict with a 'history' key)
        if isinstance(stored_data, dict) and 'history' in stored_data:
            return stored_data['history']
        
        # Assume it's the old format (just a list of messages)
        if isinstance(stored_data, list):
            return stored_data
            
        return []

    def append_to_history(self, conversation_id: str, history: List[Dict], scratchpad: List[Dict]):
        """
        Saves the full conversation context, including history and scratchpad.
        """
        key = f"{self.agent_id}:{conversation_id}"
        
        # Structure the data to be stored
        context_data = {
            "history": history,
            "scratchpad": scratchpad,
        }
        
        self._context_cache.put(key, context_data)
        logger.info(f"Saved context for key '{key}' with {len(history)} history messages and {len(scratchpad)} scratchpad entries.") 

    def save_reflexion(self, user_prompt: str, reflexion_text: str):
        """
        Saves a generated reflexion to a shared cache.
        The key is based on the prompt itself to allow for shared learning.
        """
        key = f"reflexion:{user_prompt}"
        self._reflexion_cache.put(key, reflexion_text)
        logger.info(f"Saved shared reflexion for prompt: '{user_prompt[:50]}...'") 

    def get_reflexion(self, user_prompt: str) -> Optional[str]:
        """
        Retrieves a stored reflexion for a given prompt from the shared cache.
        """
        key = f"reflexion:{user_prompt}"
        reflexion = self._reflexion_cache.get(key)
        if reflexion:
            logger.info(f"Retrieved shared reflexion for prompt: '{user_prompt[:50]}...'")
        return reflexion 