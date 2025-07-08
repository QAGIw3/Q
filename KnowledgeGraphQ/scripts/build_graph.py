# KnowledgeGraphQ/scripts/build_graph.py

import os
import logging
from gremlin_python.driver import client, serializer
from gremlin_python.process.anonymous_traversal import traversal

# --- Configuration ---
LOG_LEVEL = "INFO"
JANUSGRAPH_HOST = os.getenv("JANUSGRAPH_HOST", "localhost")
JANUSGRAPH_PORT = os.getenv("JANUSGRAPH_PORT", "8182")

# --- Logging ---
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Main Script ---

def get_graph_traversal():
    """Establishes connection to JanusGraph and returns a graph traversal source."""
    # Note: In a real app, use a more robust singleton or connection pool
    return traversal().withRemote(
        client.DriverRemoteConnection(
            f"ws://{JANUSGRAPH_HOST}:{JANUSGRAPH_PORT}/gremlin",
            'g',
            message_serializer=serializer.GraphSONSerializersV2d0()
        )
    )

def define_schema(g):
    """Defines the graph schema (vertices, edges, properties) if it doesn't exist."""
    # This is a simplified schema management example.
    # JanusGraph schema is typically defined via the management API.
    # We will ensure properties and labels exist.
    
    # Check if a known vertex exists to guess if schema is defined
    if g.V().has('doc_id', 'q_platform_overview.md-0').hasNext():
        logger.info("Schema appears to be defined already. Skipping.")
        return

    logger.info("Defining graph schema...")
    
    # Example of creating properties and indexes (idempotent)
    # In a real scenario, this would be a more complex management script.
    mgmt = g.tx().begin()
    try:
        # Properties
        if not g.V().hasLabel('Document').hasNext():
            g.addV('Document').property('name', '__placeholder__').iterate()
            g.V().has('name', '__placeholder__').drop().iterate()
        if not g.V().hasLabel('Chunk').hasNext():
            g.addV('Chunk').property('chunk_id', '__placeholder__').iterate()
            g.V().has('chunk_id', '__placeholder__').drop().iterate()
            
        logger.info("Schema definition placeholders completed.")
        mgmt.commit()
    except Exception as e:
        logger.error(f"Error defining schema: {e}")
        mgmt.rollback()
        raise

def populate_graph():
    """Populates the graph with documents and chunks."""
    g = None
    try:
        g = get_graph_traversal()
        define_schema(g)

        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        if not os.path.exists(data_dir):
            logger.error(f"Data directory not found at: {data_dir}")
            return

        files_to_process = [f for f in os.listdir(data_dir) if f.endswith(".md")]
        logger.info(f"Found {len(files_to_process)} files to populate graph.")

        for filename in files_to_process:
            # Create a vertex for the document if it doesn't exist
            doc_vertex = g.V().has('Document', 'name', filename).fold().coalesce(
                g.V().has('Document', 'name', filename),
                g.addV('Document').property('name', filename)
            ).next()
            
            logger.info(f"Processing document: {filename}")
            
            # Read the file and create chunk vertices
            # This is simplified; a real system would reuse the chunking logic
            # from the vector ingestion script.
            with open(os.path.join(data_dir, filename), 'r') as f:
                content = f.read()
            
            # Simple split by paragraph for graph representation
            chunks = [p for p in content.split('\n\n') if p.strip()]
            
            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{filename}-{i}"
                
                # Create a vertex for the chunk
                chunk_vertex = g.V().has('Chunk', 'chunk_id', chunk_id).fold().coalesce(
                    g.V().has('Chunk', 'chunk_id', chunk_id),
                    g.addV('Chunk').property('chunk_id', chunk_id).property('text', chunk_text)
                ).next()
                
                # Create an edge from the Document to the Chunk
                g.V(doc_vertex).addE('has_chunk').to(chunk_vertex).iterate()

        logger.info("Graph population complete.")

    except Exception as e:
        logger.error(f"An error occurred during graph population: {e}", exc_info=True)
    finally:
        if g:
            g.close()
            logger.info("Gremlin connection closed.")

if __name__ == "__main__":
    populate_graph() 