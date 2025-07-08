import logging

from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_vectorstore_client.models import Query
from app.core.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGModule:
    """
    Handles the Retrieval-Augmented Generation (RAG) process.
    """

    def __init__(self):
        rag_config = get_config().rag
        services_config = get_config().services
        self.collection_name = rag_config.collection_name
        self.default_top_k = rag_config.default_top_k
        self.vector_store_client = VectorStoreClient(base_url=services_config.vectorstore_url)
        # In a real app, you would also have an embedding model client here.
        # For now, we'll assume the query is already a vector or we fake it.

    async def retrieve_context(self, query_text: str) -> str:
        """
        Retrieves relevant context from the vector store for a given query text.

        Args:
            query_text: The text to search for.

        Returns:
            A formatted string of the retrieved context, ready for an LLM prompt.
        """
        logger.info(f"RAG Module: Retrieving context for query: '{query_text[:100]}...'")

        # In a real implementation, you would use a sentence transformer model
        # to convert the query_text into a vector embedding.
        # e.g., embedding = embedding_model.encode(query_text).tolist()
        # For this example, we will use a dummy vector.
        dummy_query_vector = [0.1] * 768  # Assuming a 768-dimension model

        try:
            query = Query(values=dummy_query_vector, top_k=self.default_top_k)
            search_response = await self.vector_store_client.search(
                collection_name=self.collection_name,
                queries=[query]
            )

            if not search_response.results or not search_response.results[0].hits:
                logger.warning("RAG Module: No context found for the query.")
                return ""

            # Format the retrieved chunks into a single string for the prompt
            context_chunks = [
                hit.metadata.get("text_chunk", "") 
                for hit in search_response.results[0].hits
            ]
            
            formatted_context = "\n\n---\n\n".join(filter(None, context_chunks))
            logger.info(f"RAG Module: Successfully retrieved {len(context_chunks)} context chunks.")
            
            return formatted_context

        except Exception as e:
            logger.error(f"RAG Module: Failed to retrieve context from VectorStoreQ: {e}", exc_info=True)
            # Fail gracefully by returning no context
            return ""

# Global instance for the application
rag_module = RAGModule() 