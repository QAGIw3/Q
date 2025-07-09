from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
import asyncio
import logging
from gremlin_python.structure.statics import T
from pydantic import BaseModel

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
                for res in search_response_from_client.results[0].hits: # results[0] is for the first query
                    vector_results.append(VectorStoreResult(
                        source=res.metadata.get('source', 'Unknown'),
                        content=res.metadata.get('text', ''),
                        score=res.score,
                        metadata=res.metadata
                    ))
        else:
            logger.error(f"Vector store search failed: {results[0]}", exc_info=results[0])

        # 3. Process Knowledge Graph results
        kg_result = None
        if not isinstance(results[1], Exception):
            raw_graph_data = results[1].get('result', {}).get('data', [])
            
            nodes = []
            for item in raw_graph_data:
                if item.get('@type') == 'g:Vertex':
                    vertex_value = item.get('@value', {})
                    node_id = vertex_value.get('id')
                    if not node_id: continue

                    properties = {}
                    for key, prop_list in vertex_value.get('properties', {}).items():
                        if isinstance(prop_list, list) and prop_list:
                            # Take the first property value
                            prop_value = prop_list[0].get('@value', {}).get('value')
                            if prop_value is not None:
                                properties[key] = prop_value

                    nodes.append(KGNode(
                        id=node_id,
                        label=vertex_value.get('label', 'Unknown'),
                        properties=properties
                    ))
            
            kg_result = KnowledgeGraphResult(nodes=nodes, edges=[]) # Assuming no edges for now
        else:
            logger.error(f"Knowledge graph search failed: {results[1]}", exc_info=results[1])

        # 4. Build a context and generate AI summary
        summary = "Could not generate a summary."
        model_version = None
        if vector_results or (kg_result and kg_result.nodes):
            summary_prompt = f"""Based on the following information, provide a concise, one-paragraph summary for the query: "{search_query.query}"

Semantic Search Results:
{'- ' + '\\n- '.join([res.content for res in vector_results])}

Knowledge Graph Context:
Found {len(kg_result.nodes) if kg_result else 0} related entities.

Summary:"""
            try:
                summary_request = QPChatRequest(
                    messages=[QPChatMessage(role="user", content=summary_prompt)],
                    model="q-alpha-v3-summarizer" # This now acts as a "base model" selector
                )
                summary_response = await pulse_client.get_chat_completion(summary_request)
                summary = summary_response.choices[0].message.content
                model_version = summary_response.model # Capture the model used
            except Exception as e:
                logger.error(f"Failed to generate summary from QuantumPulse: {e}", exc_info=e)
                summary = "Error generating summary."

        # 5. Synthesize the final response
        return SearchResponse(
            ai_summary=summary,
            vector_results=vector_results,
            knowledge_graph_result=kg_result,
            model_version=model_version
        )

    except Exception as e:
        logger.error(f"An unexpected error occurred during cognitive search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the search."
        ) 

class NodeNeighborsRequest(BaseModel):
    node_id: str
    hops: int = 1

@router.post("/kg-neighbors", response_model=KnowledgeGraphResult)
async def get_node_neighbors(
    request: NodeNeighborsRequest,
    user: UserClaims = Depends(get_current_user),
    kg_client: KnowledgeGraphClient = Depends(get_kg_client),
):
    """
    Fetches the neighbors of a given node in the knowledge graph.
    """
    logger.info(f"Fetching neighbors for node '{request.node_id}'")
    
    # A Gremlin query to find a node and its neighbors up to N hops
    query = f"g.V('{request.node_id}').repeat(both().simplePath()).times({request.hops}).emit().path().by(elementMap())"
    
    try:
        raw_graph_data = await kg_client.execute_gremlin_query(query)
        # We need a function to parse this path-based result into nodes and edges
        kg_result = parse_gremlin_path_to_graph(raw_graph_data)
        return kg_result
    except Exception as e:
        logger.error(f"Failed to get node neighbors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get node neighbors.")

def parse_gremlin_path_to_graph(gremlin_response: Dict[str, Any]) -> KnowledgeGraphResult:
    """
    Parses a Gremlin path() response into a KnowledgeGraphResult.
    The response contains a list of paths, and each path is a list of elements (nodes and edges).
    """
    nodes = {}
    edges = {}
    
    response_data = gremlin_response.get("result", {}).get("data", [])
    if not isinstance(response_data, list):
        return KnowledgeGraphResult(nodes=[], edges=[])

    for path in response_data:
        path_objects = path.get('objects', [])
        for i, element in enumerate(path_objects):
            element_value = element.get('@value', {})
            element_type = element.get('@type')

            if element_type == 'g:Vertex':
                node_id = element_value.get('id')
                if node_id and node_id not in nodes:
                    properties = {}
                    for key, prop_list in element_value.get('properties', {}).items():
                        if isinstance(prop_list, list) and prop_list:
                            prop_value = prop_list[0].get('@value', {}).get('value')
                            if prop_value is not None:
                                properties[key] = prop_value
                    nodes[node_id] = KGNode(id=node_id, label=element_value.get('label', 'Unknown'), properties=properties)
            
            # Reconstruct edges from the path sequence
            if i > 0 and (i % 2) != 0: # An edge appears at every odd index > 0
                source_vertex = path_objects[i-1].get('@value', {})
                target_vertex = path_objects[i+1].get('@value', {})
                edge_id = f"{source_vertex.get('id')}-{element_value.get('label')}-{target_vertex.get('id')}"

                if edge_id not in edges:
                    edges[edge_id] = KGEdge(
                        source=source_vertex.get('id'),
                        target=target_vertex.get('id'),
                        label=element_value.get('label', 'related')
                    )

    return KnowledgeGraphResult(nodes=list(nodes.values()), edges=list(edges.values())) 