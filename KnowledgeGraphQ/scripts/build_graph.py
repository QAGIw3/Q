# KnowledgeGraphQ/scripts/build_graph.py

import os
import logging
from gremlin_python.driver import client, serializer
from gremlin_python.process.anonymous_traversal import traversal

# --- Configuration ---
LOG_LEVEL = "INFO"
JANUSGRAPH_HOST = os.getenv("JANUSGRAPH_HOST", "localhost")
JANUSGRAPH_PORT = int(os.getenv("JANUSGRAPH_PORT", "8182"))
DATA_DIR = "KnowledgeGraphQ/data"

# --- Logging ---
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

def run():
    """Connects to the graph, defines a simple schema, and populates it from files."""
    try:
        remote_connection = client.DriverRemoteConnection(
            f"ws://{JANUSGRAPH_HOST}:{JANUSGRAPH_PORT}/gremlin", 'g',
            message_serializer=serializer.GraphSONSerializersV2d0()
        )
        g = traversal().withRemote(remote_connection)
        
        logger.info("Successfully connected to Gremlin server.")
        
        # Simple schema and population logic
        populate_graph(g)

    except Exception as e:
        logger.error(f"An error occurred during the graph build process: {e}", exc_info=True)
    finally:
        if 'remote_connection' in locals() and remote_connection:
            remote_connection.close()
            logger.info("Gremlin connection closed.")

def populate_graph(g):
    """Populates the graph with documents and chunks."""
    logger.info("Checking/populating graph...")

    if not os.path.exists(DATA_DIR):
        logger.error(f"Data directory not found at: {DATA_DIR}")
        return

    files_to_process = [f for f in os.listdir(DATA_DIR) if f.endswith(".md")]
    logger.info(f"Found {len(files_to_process)} files to populate graph.")

    for filename in files_to_process:
        doc_vertex = g.V().has('Document', 'name', filename).fold().coalesce(
            g.V().has('Document', 'name', filename),
            g.addV('Document').property('name', filename)
        ).next()
        
        logger.info(f"Processing document: {filename}")
        
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            content = f.read()
        
        chunks = [p for p in content.split('\n\n') if p.strip()]
        
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{filename}-{i}"
            chunk_vertex = g.V().has('Chunk', 'chunk_id', chunk_id).fold().coalesce(
                g.V().has('Chunk', 'chunk_id', chunk_id),
                g.addV('Chunk').property('chunk_id', chunk_id).property('text', chunk_text)
            ).next()
            
            # Create an edge from the Document to the Chunk
            g.V(doc_vertex).addE('has_chunk').to(chunk_vertex).iterate()

    logger.info("Graph population check complete.")

if __name__ == "__main__":
    run() 