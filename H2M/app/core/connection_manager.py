from fastapi import WebSocket
from typing import Dict, Optional

class ConnectionManager:
    def __init__(self):
        # Maps conversation_id to the active WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, conversation_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[conversation_id] = websocket

    def disconnect(self, conversation_id: str):
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]

    async def send_to_conversation(self, conversation_id: str, message: dict):
        if conversation_id in self.active_connections:
            websocket = self.active_connections[conversation_id]
            await websocket.send_json(message)

manager = ConnectionManager() 