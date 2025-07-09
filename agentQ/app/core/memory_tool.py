import logging
import uuid
import asyncio
from typing import Dict, Any

from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_vectorstore_client.models import Vector
from shared.q_memory_schemas.models import Memory
from shared.pulsar_client import shared_pulsar_client
from agentQ.app.core.toolbox import Tool
from agentQ.app.core.knowledgegraph_tool import query_knowledge_graph

logger = logging.getLogger(__name__)

# --- Configuration ---
# These should ideally be loaded from a config file or service discovery
QPULSE_API_URL = "http://localhost:8082"
VECTORSTORE_API_URL = "http://localhost:8001"
MEMORY_COLLECTION = "agent_memory"

# --- Clients ---
# In a real app, these would be managed more robustly (e.g., with dependency injection)
# qpulse_client = QuantumPulseClient(base_url=QPULSE_API_URL)
# vectorstore_client = VectorStoreClient(base_url=VECTORSTORE_API_URL)


def save_memory(memory: Dict[str, Any], config: Dict[str, Any] = None) -> str:
    """
    Saves a structured memory of a conversation to the agent's long-term memory.
    This involves creating a vector embedding of the summary and publishing the
    full memory object as a platform event.

    Args:
        memory (Dict[str, Any]): A dictionary representing the structured Memory object.
    
    Returns:
        A confirmation string indicating whether the memory was saved successfully.
    """
    try:
        # Validate and structure the memory object
        mem_obj = Memory(**memory)
        
        qpulse_client = QuantumPulseClient(base_url=config.get("qpulse_url"))
        vectorstore_client = VectorStoreClient(base_url=config.get("vector_store_url"))

        logger.info(f"Attempting to save memory: '{mem_obj.summary}'")
        
        # 1. Get embedding from QuantumPulse for the summary
        embedding = asyncio.run(qpulse_client.get_embedding("sentence-transformer", mem_obj.summary))
        
        # 2. Prepare vector for VectorStoreQ, storing the full memory object in the payload
        vector_to_upsert = Vector(
            id=mem_obj.memory_id,
            values=embedding,
            metadata=mem_obj.dict()
        )
        
        # 3. Upsert into VectorStoreQ
        asyncio.run(vectorstore_client.upsert(
            collection_name=MEMORY_COLLECTION,
            vectors=[vector_to_upsert]
        ))
        
        # 4. Publish the structured memory as a platform event
        shared_pulsar_client.publish_structured_event(
            event_type="memory.saved",
            source=mem_obj.agent_id,
            payload=mem_obj.dict()
        )
        
        logger.info(f"Successfully saved and published memory with ID: {mem_obj.memory_id}")
        return f"Memory saved successfully with ID: {mem_obj.memory_id}."
        
    except Exception as e:
        logger.error(f"Failed to save memory: {e}", exc_info=True)
        return f"Error: Failed to save memory. Details: {e}"

# --- Tool Registration ---

save_memory_tool = Tool(
    name="save_memory",
    description="Saves a structured Memory object of a conversation to the agent's long-term memory. Use this at the end of a conversation to remember key facts, entities, relationships, and the outcome.",
    func=save_memory,
    requires_context=False
)

def search_memory(query: str, top_k: int = 3, config: Dict[str, Any] = None) -> str:
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
        qpulse_client = QuantumPulseClient(base_url=config.get("qpulse_url"))
        vectorstore_client = VectorStoreClient(base_url=config.get("vector_store_url"))

        logger.info(f"Searching memory for: '{query}'")
        
        # 1. Get embedding for the query
        query_embedding = asyncio.run(qpulse_client.get_embedding("sentence-transformer", query))
        
        # 2. Search in VectorStoreQ
        search_results = asyncio.run(vectorstore_client.search(
            collection_name=MEMORY_COLLECTION,
            queries=[query_embedding],
            top_k=top_k
        ))
        
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
    description="Performs a semantic (vector-based) search of the agent's long-term memory to find information from past conversations that is relevant to the current query.",
    func=search_memory,
    requires_context=False
)

def search_memory_graph(gremlin_query: str, config: Dict[str, Any] = None) -> str:
    """
    Executes a Gremlin query against the Knowledge Graph to ask complex,
    structured questions about past memories, incidents, and their relationships.
    Use this for questions that involve filtering or traversing connections,
    e.g., 'Find all memories about 'billing-service' where the outcome was 'FAILED'.

    Args:
        gremlin_query (str): The Gremlin traversal query to execute.
    
    Returns:
        A string containing the JSON-formatted query result.
    """
    logger.info("Searching memory graph with Gremlin query", query=gremlin_query)
    # This tool is a wrapper around the generic knowledgegraph_tool,
    # but it's defined separately to give it a distinct name and description for the agent.
    # This makes the agent's "choice" of which tool to use more explicit.
    return query_knowledge_graph(gremlin_query, config)

search_memory_graph_tool = Tool(
    name="search_memory_graph",
    description="Executes a Gremlin query against the structured Knowledge Graph of memories. Use this for complex questions about past events, entities, and their relationships.",
    func=search_memory_graph
)
