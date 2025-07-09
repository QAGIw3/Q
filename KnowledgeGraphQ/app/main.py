# KnowledgeGraphQ/app/main.py
from fastapi import FastAPI
import asyncio
import logging
import json

from app.api.query import router as query_router
from app.core.pulsar_client import pulsar_client
from app.core.gremlin_client import GremlinClient
from app.core.ingestion import GraphIngestor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KnowledgeGraphQ API",
    version="0.1.0",
)

app.include_router(query_router, prefix="/api/v1/query", tags=["Query"])

# --- Pulsar Subscription Worker ---

def message_listener(consumer, msg):
    """Callback function to process messages from Pulsar."""
    try:
        payload = json.loads(msg.data())
        logger.info(f"Received message from Pulsar, ID: {msg.message_id()}")
        
        # The payload from the Zulip connector contains a 'messages' key
        zulip_messages = payload.get("messages")
        if zulip_messages and isinstance(zulip_messages, list):
            ingestor = GraphIngestor(GremlinClient.g)
            ingestor.ingest_zulip_messages(zulip_messages)
        else:
            logger.warning(f"Received payload does not contain a list of messages. Keys: {list(payload.keys())}")

        consumer.acknowledge(msg)
    except Exception as e:
        logger.error(f"Failed to process message {msg.message_id()}: {e}", exc_info=True)
        consumer.negative_acknowledge(msg)

async def start_pulsar_listener():
    """Starts the Pulsar consumer in the background."""
    logger.info("Starting Pulsar listener...")
    pulsar_client.subscribe(
        topic="persistent://public/default/knowledge-graph-ingestion",
        subscription_name="knowledge-graph-service-subscription",
        message_listener=message_listener
    )

@app.on_event("startup")
async def startup_event():
    """On startup, connect to JanusGraph and start the Pulsar listener."""
    GremlinClient.connect()
    # Run the listener in a separate task
    asyncio.create_task(start_pulsar_listener())

@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown, close connections."""
    GremlinClient.close()
    pulsar_client.close()

@app.get("/health")
async def health_check():
    return {"status": "ok"} 