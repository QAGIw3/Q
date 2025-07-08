import logging
from sentence_transformers import SentenceTransformer

from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_vectorstore_client.models import Query
from app.core.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Model Loading ---
# Load the model only once when the module is imported.
# This is a common pattern for expensive, read-only objects.
try:
    logger.info("Loading sentence transformer model for RAG...")
    EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logger.info("Sentence transformer model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load sentence transformer model: {e}", exc_info=True)
    embedding_model = None


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
        if not embedding_model:
            raise RuntimeError("Embedding model could not be loaded. RAG module is non-functional.")
        self.embedding_model = embedding_model

    async def retrieve_context(self, query_text: str) -> str:
        """
        Retrieves relevant context from the vector store for a given query text.
        """
        logger.info(f"RAG Module: Retrieving context for query: '{query_text[:100]}...'")

        # 1. Generate a real vector embedding for the user's query
        try:
            query_vector = self.embedding_model.encode(query_text).tolist()
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}", exc_info=True)
            return ""

        # 2. Search the vector store with the real vector
        try:
            query = Query(values=query_vector, top_k=self.default_top_k)
            search_response = await self.vector_store_client.search(
                collection_name=self.collection_name,
                queries=[query]
            )

            if not search_response.results or not search_response.results[0].hits:
                logger.warning("RAG Module: No context found for the query.")
                return ""

            # 3. Format the retrieved chunks into a single string for the prompt
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