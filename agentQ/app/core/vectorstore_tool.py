import logging
import asyncio

from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_vectorstore_client.models import Query
from sentence_transformers import SentenceTransformer

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration & Model Loading ---
VECTORSTORE_URL = "http://localhost:8001"
COLLECTION_NAME = "rag_document_chunks"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

try:
    logger.info("Loading sentence transformer model for VectorStoreQ tool...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logger.info("Sentence transformer model loaded successfully for tool.")
except Exception as e:
    logger.error(f"Failed to load sentence transformer model for tool: {e}", exc_info=True)
    embedding_model = None

# --- Tool Definition ---

def search_knowledge_base(query: str, top_k: int = 5, config: dict = None) -> str:
    """
    Searches the knowledge base for information relevant to a query.
    
    Args:
        query (str): The search query.
        top_k (int): The number of results to return.
        
    Returns:
        A string containing the search results, or an error message.
    """
    if not embedding_model:
        return "Error: Embedding model is not available."
    
    vector_store_url = config.get("vector_store_url")
    if not vector_store_url:
        return "Error: vector_store_url not found in tool configuration."
    
    vs_client = VectorStoreClient(base_url=vector_store_url)
    
    try:
        query_vector = embedding_model.encode(query).tolist()
        search_query = Query(values=query_vector, top_k=top_k)
        
        # Run the async search function in the current event loop
        # A more robust solution in a sync function might use asyncio.run()
        # but this can cause issues with nested loops. This is a simplification.
        loop = asyncio.get_event_loop()
        search_response = loop.run_until_complete(
            vs_client.search(collection_name=COLLECTION_NAME, queries=[search_query])
        )

        if not search_response.results or not search_response.results[0].hits:
            return "No relevant information found in the knowledge base."

        # Format the results
        results = [
            f"Result {i+1} (Score: {hit.score:.2f}):\n{hit.metadata.get('text_chunk', '')}"
            for i, hit in enumerate(search_response.results[0].hits)
        ]
        return "\n---\n".join(results)

    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}", exc_info=True)
        return f"Error: An exception occurred during the search: {e}"
    finally:
        # It's important to close the client
        loop.run_until_complete(vs_client.close())


# --- Tool Registration Object ---

vectorstore_tool = Tool(
    name="search_knowledge_base",
    description="Searches the platform's knowledge base for documents, text chunks, and information relevant to a user's query. Use this to find answers to specific questions.",
    func=search_knowledge_base
)

def search_codebase(query: str, top_k: int = 5, config: dict = None) -> str:
    """
    Searches the platform's source code for functions, classes, or logic relevant to a query.
    
    Args:
        query (str): The search query (e.g., "function to dispatch tasks", "class for RAG module").
        top_k (int): The number of code chunks to return.
        config (dict): The agent's service configuration, including the vector_store_url.
        
    Returns:
        A string containing the most relevant code chunks found.
    """
    if not embedding_model:
        return "Error: Embedding model is not available for code search."
    
    vector_store_url = config.get("vector_store_url")
    if not vector_store_url:
        return "Error: vector_store_url not found in tool configuration."

    vs_client = VectorStoreClient(base_url=vector_store_url)
    
    async def do_search():
        try:
            query_vector = embedding_model.encode(query).tolist()
            search_query = Query(values=query_vector, top_k=top_k)
            
            search_response = await vs_client.search(
                collection_name="code_documentation", # Use the new collection
                queries=[search_query]
            )

            if not search_response.results or not search_response.results[0].hits:
                return "No relevant code found in the knowledge base."

            results = []
            for hit in search_response.results[0].hits:
                metadata = hit.metadata
                file_path = metadata.get('file_path', 'unknown')
                code_chunk = metadata.get('code_chunk', '')
                results.append(f"// From: {file_path}\n// Score: {hit.score:.2f}\n\n{code_chunk}")
            
            return "\\n---\\n".join(results)
        finally:
            await vs_client.close()

    try:
        return asyncio.run(do_search())
    except Exception as e:
        logger.error(f"Error searching codebase: {e}", exc_info=True)
        return f"Error: An exception occurred during the code search: {e}"

code_search_tool = Tool(
    name="search_codebase",
    description="Searches the platform's own source code to find relevant functions, classes, or implementation details. Use this to answer questions about how the platform works internally.",
    func=search_codebase
) 