import logging
import uuid

from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_vectorstore_client.models import Vector
from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
# These should ideally be loaded from a config file or service discovery
QPULSE_API_URL = "http://localhost:8082"
VECTORSTORE_API_URL = "http://localhost:8001"
MEMORY_COLLECTION = "agent_memory"

# --- Clients ---
# In a real app, these would be managed more robustly (e.g., with dependency injection)
qpulse_client = QuantumPulseClient(base_url=QPULSE_API_URL)
vectorstore_client = VectorStoreClient(base_url=VECTORSTORE_API_URL)


def save_memory(summary: str) -> str:
    """
    Saves a summary of a conversation to the agent's long-term memory.
    This involves creating a vector embedding of the summary and storing both
    the text and the vector in the memory collection.

    Args:
        summary (str): A concise summary of the key information from a conversation.
    
    Returns:
        A confirmation string indicating whether the memory was saved successfully.
    """
    try:
        logger.info(f"Attempting to save memory: '{summary}'")
        
        # 1. Get embedding from QuantumPulse
        # Using a generic sentence embedding model
        embedding = qpulse_client.get_embedding("sentence-transformer", summary)
        
        # 2. Prepare vector for VectorStoreQ
        memory_id = str(uuid.uuid4())
        vector_to_upsert = Vector(
            id=memory_id,
            vector=embedding,
            payload={"summary_text": summary}
        )
        
        # 3. Upsert into VectorStoreQ
        vectorstore_client.upsert(
            collection_name=MEMORY_COLLECTION,
            vectors=[vector_to_upsert]
        )
        
        logger.info(f"Successfully saved memory with ID: {memory_id}")
        return f"Memory saved successfully with ID: {memory_id}."
        
    except Exception as e:
        logger.error(f"Failed to save memory: {e}", exc_info=True)
        return f"Error: Failed to save memory. Details: {e}"

# --- Tool Registration ---

save_memory_tool = Tool(
    name="save_memory",
    description="Saves a textual summary of a conversation to the agent's long-term memory. Use this at the end of a conversation to remember key facts.",
    func=save_memory
)

def search_memory(query: str, top_k: int = 3) -> str:
    """
    Searches the agent's long-term memory for relevant information.
    This is useful for recalling facts from past conversations. It finds the
    most similar memories to the given query.

    Args:
        query (str): The question or topic to search for in memory.
        top_k (int): The number of relevant memories to return.
    
    Returns:
        A string containing the most relevant memories found.
    """
    try:
        logger.info(f"Searching memory for: '{query}'")
        
        # 1. Get embedding for the query
        query_embedding = qpulse_client.get_embedding("sentence-transformer", query)
        
        # 2. Search in VectorStoreQ
        search_results = vectorstore_client.search(
            collection_name=MEMORY_COLLECTION,
            queries=[query_embedding],
            top_k=top_k
        )
        
        # The result is a list of lists. We want the first list.
        if not search_results or not search_results[0]:
            return "No relevant memories found."
            
        # 3. Format the results for the agent
        formatted_results = []
        for result in search_results[0]:
            # The payload contains the original summary text
            text = result.get("payload", {}).get("summary_text", "No text found.")
            score = result.get("score", 0.0)
            formatted_results.append(f"- (Score: {score:.2f}) {text}")
        
        logger.info(f"Found {len(formatted_results)} relevant memories.")
        return "Found relevant memories:\n" + "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Failed to search memory: {e}", exc_info=True)
        return f"Error: Failed to search memory. Details: {e}"

search_memory_tool = Tool(
    name="search_memory",
    description="Searches the agent's long-term memory to find information from past conversations that is relevant to the current query.",
    func=search_memory
)
