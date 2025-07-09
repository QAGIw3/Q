import logging
import httpx
import asyncio
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
KNOWLEDGE_GRAPH_URL = "http://localhost:8083" # Assuming KG service runs on this port

# --- Tool Definition ---

def query_knowledge_graph(gremlin_query: str) -> str:
    """
    Executes a Gremlin query against the platform's knowledge graph.
    Use this to find relationships between entities, discover structured information,
    or ask complex questions about how data is connected.
    
    Args:
        gremlin_query (str): The Gremlin traversal query to execute.
        
    Returns:
        A string containing the JSON-formatted query result, or an error message.
    """
    try:
        url = f"{KNOWLEDGE_GRAPH_URL}/query"
        
        async def do_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"query": gremlin_query}, timeout=30.0)
                response.raise_for_status()
                return response.json()
        
        response_data = asyncio.run(do_request())
        
        logger.info(f"Successfully queried KnowledgeGraph. Query: {gremlin_query}")
        return str(response_data.get("result", "No result found."))

    except httpx.HTTPStatusError as e:
        error_details = e.response.json().get("detail", e.response.text)
        logger.error(f"Error querying KnowledgeGraph: {e.response.status_code} - {error_details}")
        return f"Error: Failed to query KnowledgeGraph. Status: {e.response.status_code}. Detail: {error_details}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while querying KnowledgeGraph: {e}", exc_info=True)
        return f"Error: An unexpected error occurred: {e}"


# --- Tool Registration Object ---

knowledgegraph_tool = Tool(
    name="query_knowledge_graph",
    description="Executes a Gremlin query against the platform's knowledge graph to find structured data and relationships between entities. Use this when you need to answer questions like 'What is related to X?' or 'How does A connect to B?'.",
    func=query_knowledge_graph
) 