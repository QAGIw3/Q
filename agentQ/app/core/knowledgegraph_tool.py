import logging
import httpx
import asyncio
from typing import Dict, Any
import time

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
KNOWLEDGE_GRAPH_URL = "http://localhost:8083" # Assuming KG service runs on this port

# --- Tool Definition ---

def query_knowledge_graph(gremlin_query: str, config: Dict[str, Any] = None) -> str:
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
        knowledge_graph_url = config.get("knowledge_graph_url")
        if not knowledge_graph_url:
            return "Error: knowledge_graph_url not found in tool configuration."

        url = f"{knowledge_graph_url}/query"
        
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


def summarize_stream_activity(stream_name: str, hours_ago: int = 24, config: Dict[str, Any] = None) -> str:
    """
    Summarizes recent activity in a specific Zulip stream within a given time window.
    Provides the total number of messages and the top 5 most active users.

    Args:
        stream_name (str): The name of the Zulip stream to analyze.
        hours_ago (int): The time window in hours to look back for activity. Defaults to 24.
    
    Returns:
        A summary string of the recent activity.
    """
    timestamp_since = (asyncio.run(asyncio.sleep(0, result=int(time.time()))) - (hours_ago * 3600))

    query = f"""
    g.V().has('stream', 'name', '{stream_name}').as_('s')
        .in('in_stream').has('message', 'timestamp', gt({timestamp_since})).as_('m')
        .in('sent').as_('u')
        .select('s', 'm', 'u')
        .group()
        .by(select('s').values('name'))
        .by(
            project('total_messages', 'top_users')
            .by(count(local))
            .by(
                select('u').values('full_name').groupCount().order(local).by(values, decr).limit(local, 5)
            )
        )
    """
    
    # We re-use the generic query function to execute this complex query
    result = query_knowledge_graph(query, config=config)
    
    # The agent can parse this structured string to answer the user
    return f"Activity summary for stream '{stream_name}' in the last {hours_ago} hours: {result}"


def find_experts_on_topic(topic: str, config: Dict[str, Any] = None) -> str:
    """
    Identifies users who have talked the most about a specific topic.
    It searches message content for the topic string and returns the top 5 most frequent posters.

    Args:
        topic (str): The topic keyword to search for in messages.
    
    Returns:
        A string listing the top experts on the topic.
    """
    # Using 'tokenFuzzy' would be better here if the graph index supports it.
    # For now, we use a simple 'contains' text predicate.
    query = f"""
    g.V().has('message', 'content', textContains('{topic}'))
        .in('sent')
        .values('full_name')
        .groupCount()
        .order(local).by(values, decr)
        .limit(local, 5)
    """
    
    result = query_knowledge_graph(query, config=config)
    
    return f"Top experts on the topic '{topic}': {result}"


# --- Tool Registration Object ---

knowledgegraph_tool = Tool(
    name="query_knowledge_graph",
    description="Executes a Gremlin query against the platform's knowledge graph to find structured data and relationships between entities. Use this when you need to answer questions like 'What is related to X?' or 'How does A connect to B?'.",
    func=query_knowledge_graph
)

summarize_activity_tool = Tool(
    name="summarize_stream_activity",
    description="Summarizes recent activity in a specific Zulip stream, including message counts and top contributors.",
    func=summarize_stream_activity
)

find_experts_tool = Tool(
    name="find_experts_on_topic",
    description="Finds users who have talked the most about a specific topic by searching message contents.",
    func=find_experts_on_topic
) 