from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncio
import logging
from gremlin_python.structure.statics import T

from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from shared.q_vectorstore_client.client import VectorStoreClient, Query as VectorQuery
from shared.q_knowledgegraph_client.client import KnowledgeGraphClient
from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import QPChatRequest, QPChatMessage

from managerQ.app.models import (
    SearchQuery, 
    SearchResponse, 
    VectorStoreResult, 
    KnowledgeGraphResult, 
    KGNode, 
    KGEdge
)
from managerQ.app.dependencies import get_vector_store_client, get_kg_client, get_pulse_client

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=SearchResponse)
async def cognitive_search(
    search_query: SearchQuery,
    user: UserClaims = Depends(get_current_user),
    vector_store_client: VectorStoreClient = Depends(get_vector_store_client),
    kg_client: KnowledgeGraphClient = Depends(get_kg_client),
    pulse_client: QuantumPulseClient = Depends(get_pulse_client)
):
    """
    Performs a cognitive search by orchestrating calls to VectorStoreQ,
    KnowledgeGraphQ, and QuantumPulse.
    """
    try:
        # 1. Asynchronously query the backend services in parallel
        vector_query = VectorQuery(query=search_query.query, top_k=5)
        # Assuming a default collection name for now
        semantic_future = vector_store_client.search(collection_name="documents", queries=[vector_query])
        
        # A simple Gremlin query to find entities by name (case-insensitive)
        gremlin_query = f"g.V().has('name', textContains('{search_query.query}')).elementMap().limit(10)"
        graph_future = kg_client.execute_gremlin_query(gremlin_query)
        
        results = await asyncio.gather(semantic_future, graph_future, return_exceptions=True)
        
        # 2. Process Vector Store results
        vector_results = []
        if not isinstance(results[0], Exception):
            # The client returns a SearchResponse, we need to unpack it.
            search_response_from_client = results[0]
            if search_response_from_client.results:
                for res in search_response_from_client.results[0].results: # Results for the first query
                    vector_results.append(VectorStoreResult(
                        source=res.metadata.get('source', 'Unknown'),
                        content=res.text,
                        score=res.score,
                        metadata=res.metadata
                    ))
        else:
            logger.error(f"Vector store search failed: {results[0]}", exc_info=results[0])

        # 3. Process Knowledge Graph results
        kg_result = None
        if not isinstance(results[1], Exception):
            raw_graph_data = results[1].get('result', {}).get('data', [])
            
            nodes_map = {}
            edges = []

            for item in raw_graph_data:
                # Gremlin's elementMap returns a map for each element
                # We need to process both vertices and the edges if they exist
                node_id = item.get(T.id)
                if node_id and node_id not in nodes_map:
                    properties = {k: v for k, v in item.items() if k not in [T.id, T.label]}
                    nodes_map[node_id] = KGNode(
                        id=node_id,
                        label=item.get(T.label, 'Unknown'),
                        properties=properties
                    )
            
            # This part is a simplification. A full graph traversal would be needed
            # to reconstruct edges if they were also queried and returned.
            # For now, we are just returning found nodes.
            kg_result = KnowledgeGraphResult(nodes=list(nodes_map.values()), edges=[])
        else:
            logger.error(f"Knowledge graph search failed: {results[1]}", exc_info=results[1])

        # 4. Build a context and generate AI summary
        summary = "Could not generate a summary."
        if vector_results or (kg_result and kg_result.nodes):
            summary_prompt = f"""Based on the following information, provide a concise, one-paragraph summary for the query: "{search_query.query}"

Semantic Search Results:
{'- ' + '\\n- '.join([res.content for res in vector_results])}

Knowledge Graph Context:
Found {len(kg_result.nodes)} related entities.

Summary:"""
            try:
                summary_request = QPChatRequest(
                    messages=[QPChatMessage(role="user", content=summary_prompt)],
                    model="q-alpha-v3-summarizer"
                )
                summary_response = await pulse_client.get_chat_completion(summary_request)
                summary = summary_response.choices[0].message.content
            except Exception as e:
                logger.error(f"Failed to generate summary from QuantumPulse: {e}", exc_info=e)
                summary = "Error generating summary."

        # 5. Synthesize the final response
        return SearchResponse(
            ai_summary=summary,
            vector_results=vector_results,
            knowledge_graph_result=kg_result
        )

    except Exception as e:
        logger.error(f"An unexpected error occurred during cognitive search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the search."
        ) 