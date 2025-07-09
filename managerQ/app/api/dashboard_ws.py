import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict

from managerQ.app.models import WorkflowEvent

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("New dashboard client connected.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("Dashboard client disconnected.")

    async def broadcast(self, message: Dict):
        # In a production system with multiple managerQ instances, this would
        # need to be backed by a pub/sub system like Pulsar to ensure all
        # clients receive all messages, regardless of which instance they're
        # connected to. For now, this simple in-memory broadcast is sufficient.
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

async def broadcast_workflow_event(event: WorkflowEvent):
    """A helper function to allow other modules to broadcast events."""
    await manager.broadcast(event.dict())

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from the client, just keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket) 