import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import pulsar
import json
import asyncio

from managerQ.app.models import WorkflowEvent
from managerQ.app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.client: pulsar.Client = None
        self.producer: pulsar.Producer = None

    def startup(self):
        """Connects to Pulsar and creates a producer."""
        try:
            self.client = pulsar.Client(settings.pulsar.service_url)
            self.producer = self.client.create_producer(settings.pulsar.topics.dashboard_events)
            logger.info("ConnectionManager connected to Pulsar and created producer.")
        except Exception as e:
            logger.error(f"Failed to initialize Pulsar client for ConnectionManager: {e}", exc_info=True)
            raise

    def shutdown(self):
        """Closes the Pulsar producer and client."""
        if self.producer:
            self.producer.close()
        if self.client:
            self.client.close()
        logger.info("ConnectionManager disconnected from Pulsar.")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        logger.info("New dashboard client connected via WebSocket.")

    def disconnect(self, websocket: WebSocket):
        logger.info("Dashboard client disconnected via WebSocket.")

    async def broadcast(self, message: Dict):
        if not self.producer:
            logger.error("Cannot broadcast: Pulsar producer is not available.")
            return
        
        self.producer.send(json.dumps(message).encode('utf-8'))

manager = ConnectionManager()

async def broadcast_workflow_event(event: WorkflowEvent):
    """A helper function to allow other modules to broadcast events."""
    await manager.broadcast(event.dict())

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Create a unique subscription name for this client
    subscription_name = f"dashboard-client-{websocket.client.host}-{websocket.client.port}"
    
    consumer = None
    try:
        client = pulsar.Client(settings.pulsar.service_url)
        consumer = client.subscribe(
            settings.pulsar.topics.dashboard_events,
            subscription_name=subscription_name,
            consumer_type=pulsar.ConsumerType.Exclusive # Each client gets all messages
        )
        
        while True:
            msg = consumer.receive()
            try:
                message_data = json.loads(msg.data().decode('utf-8'))
                await websocket.send_json(message_data)
                consumer.acknowledge(msg)
            except Exception as e:
                logger.error(f"Error processing message or sending to websocket: {e}", exc_info=True)
                consumer.negative_acknowledge(msg)
                
    except WebSocketDisconnect:
        logger.info(f"Client {subscription_name} disconnected.")
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint for {subscription_name}: {e}", exc_info=True)
    finally:
        if consumer:
            consumer.close()
        if 'client' in locals() and client:
            client.close()
        manager.disconnect(websocket) 