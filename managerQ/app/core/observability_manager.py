# managerQ/app/core/observability_manager.py
import asyncio
import logging
from typing import List
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)

class ObservabilityManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("New client connected to observability websocket.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        """Broadcasts data to all connected clients."""
        # This can be slow if there are many connections.
        # A more robust solution might use a message queue.
        for connection in self.active_connections:
            await connection.send_text(json.dumps(data))

# Singleton instance
observability_manager = ObservabilityManager() 