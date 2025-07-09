# managerQ/app/api/observability_ws.py
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from managerQ.app.core.observability_manager import observability_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint to stream real-time observability data.
    """
    await observability_manager.connect(websocket)
    try:
        while True:
            # The manager will push data to the client.
            # We can also receive messages from the client if needed in the future.
            await asyncio.sleep(1) 
    except WebSocketDisconnect:
        observability_manager.disconnect(websocket)
        logger.info("Client disconnected from observability websocket.") 