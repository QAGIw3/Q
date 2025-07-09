import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import pulsar
import json
import asyncio
import threading

from managerQ.app.models import WorkflowEvent
from managerQ.app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class DashboardConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._pulsar_client: pulsar.Client = None
        self._pulsar_consumer: pulsar.Consumer = None
        self._running = False
        self._thread: threading.Thread = None

    def startup(self):
        """Connects to Pulsar and starts a consumer in a background thread."""
        if self._running:
            return
        
        logger.info("DashboardConnectionManager starting up...")
        self._pulsar_client = pulsar.Client(settings.pulsar.service_url)
        self._pulsar_consumer = self._pulsar_client.subscribe(
            settings.pulsar.topics.dashboard_events,
            subscription_name="managerq-dashboard-broadcaster-sub",
            consumer_type=pulsar.ConsumerType.Shared # Shared so we can scale managerQ if needed
        )
        self._running = True
        self._thread = threading.Thread(target=self._consumer_loop, daemon=True)
        self._thread.start()
        logger.info("DashboardConnectionManager started.")

    def shutdown(self):
        """Closes the Pulsar consumer and client."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._pulsar_consumer:
            self._pulsar_consumer.close()
        if self._pulsar_client:
            self._pulsar_client.close()
        logger.info("DashboardConnectionManager shut down.")
    
    def _consumer_loop(self):
        while self._running:
            try:
                msg = self._pulsar_consumer.receive(timeout_millis=1000)
                message_data = json.loads(msg.data().decode('utf-8'))
                # The broadcast needs to be async, but this loop is sync.
                # We can run it in the asyncio event loop of the main thread.
                asyncio.run(self.broadcast(message_data))
                self._pulsar_consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in DashboardConnectionManager consumer loop: {e}", exc_info=True)
                if 'msg' in locals():
                    self._pulsar_consumer.negative_acknowledge(msg)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New dashboard client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Dashboard client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict):
        # Create a list of tasks to send messages to all clients concurrently
        tasks = [client.send_json(message) for client in self.active_connections]
        # Wait for all messages to be sent
        await asyncio.gather(*tasks, return_exceptions=True)


# This manager instance will be shared across the application
manager = DashboardConnectionManager()

# We still need a way for other parts of the app to publish events.
# They shouldn't have to know about the manager, just about Pulsar.
# So we will create a SEPARATE producer when needed.
async def broadcast_workflow_event(event: WorkflowEvent):
    """A helper function to allow other modules to broadcast events to the dashboard topic."""
    # This is a bit inefficient to create a client/producer for each event.
    # A better approach would be to have a shared producer instance.
    # For now, this maintains the decoupled nature.
    client = None
    producer = None
    try:
        client = pulsar.Client(settings.pulsar.service_url)
        producer = client.create_producer(settings.pulsar.topics.dashboard_events)
        producer.send(json.dumps(event.dict()).encode('utf-8'))
        producer.flush()
    except Exception as e:
        logger.error(f"Failed to broadcast workflow event: {e}", exc_info=True)
    finally:
        if producer:
            producer.close()
        if client:
            client.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive, but all broadcasting is handled by the manager
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint: {e}", exc_info=True)
        manager.disconnect(websocket) 