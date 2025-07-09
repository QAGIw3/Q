# KnowledgeGraphQ/app/core/gremlin_client.py
import logging
from gremlin_python.driver import client, serializer
from gremlin_python.process.anonymous_traversal import traversal

logger = logging.getLogger(__name__)

class GremlinClient:
    """A client for interacting with a Gremlin-compatible graph database."""

    def __init__(self, host: str, port: int):
        self._connection = None
        self.g = None
        self.host = host
        self.port = port

    def connect(self):
        """Establishes the connection to the Gremlin server."""
        if self._connection:
            logger.info("Gremlin client already connected.")
            return

        try:
            self._connection = client.DriverRemoteConnection(
                f"ws://{self.host}:{self.port}/gremlin",
                'g',
                message_serializer=serializer.GraphSONSerializersV2d0()
            )
            self.g = traversal().withRemote(self._connection)
            logger.info(f"Successfully connected to Gremlin server at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Gremlin server: {e}", exc_info=True)
            raise

    def close(self):
        """Closes the connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            self.g = None
            logger.info("Gremlin connection closed.")

    def execute_query(self, query: str) -> list:
        """Executes a raw Gremlin query."""
        if not self.g:
            raise ConnectionError("Not connected to Gremlin server.")
        
        try:
            # This is a simplified execution. A more robust implementation
            # would use bytecode, but raw strings are fine for this use case.
            result = self.g.V().inject(1).toList() # A simple query to test connection
            # A real implementation would need a way to parse and execute the string query.
            # For now, we'll return a placeholder.
            # result = self.g.cypher(query).toList() # If using Cypher
            return [{"message": "Query execution is not fully implemented yet.", "query": query}]
        except Exception as e:
            logger.error(f"Failed to execute Gremlin query: {e}", exc_info=True)
            raise

# For now, we'll create a placeholder instance.
# In a real app, this would be configured and managed in the main app.
gremlin_client = GremlinClient(host="localhost", port=8182) 