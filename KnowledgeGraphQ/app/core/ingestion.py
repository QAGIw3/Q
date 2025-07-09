import logging
from typing import Dict, Any, List

from app.core.gremlin_client import GremlinClient

logger = logging.getLogger(__name__)

class GraphIngestor:
    """
    Handles the logic of ingesting structured data into the JanusGraph database.
    """

    def __init__(self, g: GremlinClient):
        self.g = g

    def ingest_zulip_messages(self, messages: List[Dict[str, Any]]):
        """
        Processes a list of Zulip messages and ingests them into the graph.
        """
        logger.info(f"Starting ingestion of {len(messages)} Zulip messages.")
        for msg in messages:
            try:
                self._ingest_single_message(msg)
            except Exception as e:
                logger.error(f"Failed to ingest message ID {msg.get('id')}: {e}", exc_info=True)
        logger.info("Finished ingesting batch of Zulip messages.")

    def _ingest_single_message(self, msg: Dict[str, Any]):
        """
        Ingests a single Zulip message, creating vertices and edges as needed.
        This process is idempotent.
        """
        # 1. Create or update the User vertex
        # Note: In a production system, user details might come from a different source.
        sender_id = msg.get("sender_id")
        user_vertex = self.g.V().has("user", "user_id", sender_id).fold().coalesce(
            self.g.unfold(),
            self.g.addV("user")
                .property("user_id", sender_id)
                .property("full_name", msg.get("sender_full_name"))
                .property("email", msg.get("sender_email"))
                .property("source", "zulip")
        ).next()

        # 2. Create or update the Stream vertex
        stream_id = msg.get("stream_id")
        stream_vertex = self.g.V().has("stream", "stream_id", stream_id).fold().coalesce(
            self.g.unfold(),
            self.g.addV("stream")
                .property("stream_id", stream_id)
                .property("name", msg.get("display_recipient"))
                .property("source", "zulip")
        ).next()

        # 3. Create the Message vertex
        msg_id = msg.get("id")
        message_vertex = self.g.V().has("message", "message_id", msg_id).fold().coalesce(
            self.g.unfold(),
            self.g.addV("message")
                .property("message_id", msg_id)
                .property("content", msg.get("content"))
                .property("timestamp", msg.get("timestamp"))
                .property("source", "zulip")
        ).next()

        # 4. Create the edges
        # User -> SENT -> Message
        self.g.V(user_vertex).addE("sent").to(message_vertex).iterate()
        # Message -> IN_STREAM -> Stream
        self.g.V(message_vertex).addE("in_stream").to(stream_vertex).iterate()
        
        logger.info(f"Successfully ingested message {msg_id}.")

# Instantiate the ingestor for use in the listener
graph_ingestor = GraphIngestor(GremlinClient.g)
