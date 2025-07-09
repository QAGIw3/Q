from fastapi import APIRouter, Query, Depends
from typing import List, Dict, Any
import asyncio

from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_knowledgegraph_client.client import KnowledgeGraphClient
from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import QPChatRequest, QPChatMessage

router = APIRouter()

# In a real app, these clients would be managed more robustly
# (e.g., with a dependency injection system).
vector_store_client = VectorStoreClient()
kg_client = KnowledgeGraphClient()
pulse_client = QuantumPulseClient()

@router.get("/")
async def cognitive_search(
    query: str = Query(..., min_length=3),
    user: UserClaims = Depends(get_current_user)
):
    """
    Performs a cognitive search by orchestrating calls to VectorStoreQ,
    KnowledgeGraphQ, and QuantumPulse.
    """
    # 1. Asynchronously query the backend services in parallel
    semantic_future = vector_store_client.search(collection_name="documents", query=query, limit=5)
    graph_future = kg_client.find_related_entities(query, hops=1)
    
    # Wait for the initial data retrieval to complete
    results = await asyncio.gather(semantic_future, graph_future, return_exceptions=True)
    
    semantic_results = results[0] if not isinstance(results[0], Exception) else []
    graph_results = results[1] if not isinstance(results[1], Exception) else {"nodes": [], "edges": []}

    # 2. Build a context prompt for the summarization LLM
    summary_prompt = f"""
    Based on the following information, provide a concise, one-paragraph summary for the query: "{query}"

    Semantic Search Results:
    {'- ' + '\\n- '.join([res.get('text', '') for res in semantic_results])}

    Knowledge Graph Context:
    Found {len(graph_results.get('nodes', []))} related entities.

    Summary:
    """

    # 3. Call QuantumPulse to generate the summary
    try:
        summary_request = QPChatRequest(
            messages=[QPChatMessage(role="user", content=summary_prompt)],
            model="q-alpha-v3-summarizer" # A hypothetical summarizer model
        )
        summary_response = await pulse_client.get_chat_completion(summary_request)
        summary = summary_response.choices[0].message.content
    except Exception as e:
        summary = f"Could not generate summary: {e}"

    # 4. Synthesize the final response
    return {
        "summary": summary,
        "semantic_results": semantic_results,
        "graph_results": graph_results
    } 