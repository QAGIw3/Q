# KnowledgeGraphQ/app/core/gremlin_client.py
import logging
from typing import Dict, Any, List
from gremlin_python.driver import client, serializer
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.strategies import *

logger = logging.getLogger(__name__)

class GremlinClient:
    """A client for interacting with a Gremlin-compatible graph database."""

    def __init__(self, host: str, port: int):
        self._connection = None
        self.g = None
        self.host = host
        self.port = port
        # In a containerized setup, janusgraph is the service name
        self.uri = f"ws://{self.host}:{self.port}/gremlin"

    def connect(self):
        """Establishes the connection to the Gremlin server."""
        if self._connection and not self._connection.closed:
            logger.info("Gremlin client already connected.")
            return

        try:
            self._connection = client.DriverRemoteConnection(
                self.uri,
                'g',
                message_serializer=serializer.GraphSONSerializersV2d0()
            )
            self.g = traversal().withRemote(self._connection)
            logger.info(f"Successfully connected to Gremlin server at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Gremlin server: {e}", exc_info=True)
            # Re-raise the exception to be handled by the caller
            raise ConnectionError(f"Failed to connect to Gremlin at {self.uri}") from e

    def close(self):
        """Closes the connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self.g = None
            logger.info("Gremlin connection closed.")

    def _ensure_connected(self):
        if not self.g:
            self.connect()

    def execute_query(self, query: str) -> list:
        """Executes a raw Gremlin query. Note: Use with caution."""
        self._ensure_connected()
        logger.debug(f"Executing raw Gremlin query: {query}")
        try:
            # This relies on the server supporting string-based script execution
            result_set = self._connection.client.submit(query)
            # The future result needs to be iterated to get all results
            items = result_set.all().result()
            return items
        except Exception as e:
            logger.error(f"Failed to execute Gremlin query '{query}': {e}", exc_info=True)
            raise

    def upsert_vertex(self, label: str, properties: Dict[str, Any], id_key: str = "uid"):
        """
        Creates a vertex with a given label and properties, or updates it if it already exists.
        The vertex is identified by the `id_key` in its properties.
        """
        self._ensure_connected()
        if id_key not in properties:
            raise ValueError(f"Vertex properties must contain the id_key '{id_key}'")

        id_val = properties[id_key]
        
        # Start a traversal
        t = self.g.V().has(label, id_key, id_val)
        
        # Check if the vertex exists.
        if t.hasNext():
            # Vertex exists, update properties
            v_update = t.next()
            props_to_update = self.g.V(v_update)
            for key, value in properties.items():
                if key != id_key: # Don't update the ID property itself
                    props_to_update = props_to_update.property(key, value)
            props_to_update.iterate()
            logger.info(f"Updated vertex '{label}' with {id_key} '{id_val}'")
        else:
            # Vertex does not exist, create it
            v_create = self.g.addV(label)
            for key, value in properties.items():
                v_create = v_create.property(key, value)
            v_create.iterate()
            logger.info(f"Created vertex '{label}' with {id_key} '{id_val}'")

    def upsert_edge(self, label: str, from_vertex_id: str, to_vertex_id: str, from_vertex_label: str, to_vertex_label: str, id_key: str = "uid"):
        """
        Creates a directed edge between two vertices if it does not already exist.
        """
        self._ensure_connected()

        # Find the source and destination vertices
        from_v = self.g.V().has(from_vertex_label, id_key, from_vertex_id)
        to_v = self.g.V().has(to_vertex_label, id_key, to_vertex_id)

        # Check if edge already exists. If not, create it.
        # Coalesce pattern: if the first traversal returns a result, use it. Otherwise, run the second traversal.
        self.g.V(from_v).outE(label).where(__.inV().is_(to_v)).fold().coalesce(
            __.unfold(), # Edge exists, do nothing
            __.addE(label).from_(from_v).to(to_v) # Edge does not exist, create it
        ).iterate()
        
        logger.info(f"Ensured edge '{label}' exists from '{from_vertex_id}' to '{to_vertex_id}'")


# In a real app, this would be configured and managed in the main app.
# The host 'janusgraph' is the service name in Docker Compose/Kubernetes.
gremlin_client = GremlinClient(host="janusgraph", port=8182) 