import structlog
import yaml
import httpx
import asyncio

from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.context import ContextManager
from agentQ.app.core.knowledgegraph_tool import knowledgegraph_tool # To write to the graph

logger = structlog.get_logger("knowledge_engineer_agent")

# --- Agent Definition ---
AGENT_ID = "knowledge-engineer-agent-01"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"

KNOWLEDGE_ENGINEER_SYSTEM_PROMPT = """
You are a Knowledge Engineer AI. Your sole purpose is to enrich the platform's Knowledge Graph by extracting structured information from unstructured documents.

**Your Workflow:**
1.  Use the `get_unprocessed_documents` tool to fetch a batch of recently added text documents.
2.  For each document, carefully read the text and identify key entities. Entities can be:
    -   **Services**: (e.g., 'QuantumPulse', 'managerQ', 'VectorStoreQ')
    -   **Technologies**: (e.g., 'Kubernetes', 'Pulsar', 'React', 'FastAPI')
    -   **Concepts**: (e.g., 'RAG', 'multi-agent system', 'fine-tuning')
3.  For each document, generate a series of `upsert_vertex` and `upsert_edge` operations using the `knowledgegraph_tool` to represent the relationships you found. For example, if a document mentions that 'H2M uses VectorStoreQ', you would create an edge `('H2M', 'USES', 'VectorStoreQ')`.
4.  Once you have processed all documents in the batch, use the `finish` action with a summary of the entities and relationships you added.

This is an automated, ongoing task. Begin.
"""

# --- Tools for the Knowledge Engineer ---

def get_unprocessed_documents(config: dict) -> str:
    """
    Retrieves a batch of unprocessed documents from the vector store.
    (This is a placeholder for a more robust implementation).
    """
    # In a real system, we would have a mechanism to track which documents
    # have been processed. For now, we'll just grab the latest N chunks.
    vector_store_url = config.get("vector_store_url")
    if not vector_store_url:
        return "Error: vector_store_url not configured."
    
    # This is a simplified search query to get some recent documents.
    search_query = {
        "collection_name": "rag_document_chunks",
        "queries": [{"values": [0.0] * 384, "top_k": 10}] # Placeholder query
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(f"{vector_store_url}/v1/search", json=search_query)
            response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error fetching documents: {e}"

unprocessed_docs_tool = Tool(
    name="get_unprocessed_documents",
    description="Retrieves a batch of recently added documents that need to be processed and added to the Knowledge Graph.",
    func=get_unprocessed_documents
)

def setup_knowledge_engineer_agent(config: dict):
    """
    Initializes the toolbox and context manager for the Knowledge Engineer agent.
    """
    logger.info("Setting up Knowledge Engineer Agent", agent_id=AGENT_ID)
    
    toolbox = Toolbox()
    toolbox.register_tool(unprocessed_docs_tool)
    toolbox.register_tool(knowledgegraph_tool) # To write the final graph
    
    context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=AGENT_ID)
    context_manager.connect()
    
    return toolbox, context_manager 