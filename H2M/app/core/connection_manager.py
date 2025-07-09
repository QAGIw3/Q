from fastapi import WebSocket
from typing import Dict, Optional

class ConnectionManager:
    def __init__(self):
        # Maps conversation_id to the active WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, connection_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[connection_id] = websocket

    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

    def re_key_connection(self, old_key: str, new_key: str, websocket: WebSocket):
        """Updates the key for a connection, e.g., from a temp user ID to a stable conversation ID."""
        if old_key in self.active_connections:
            self.disconnect(old_key)
        self.active_connections[new_key] = websocket

    async def send_to_conversation(self, conversation_id: str, message: dict):
        if conversation_id in self.active_connections:
            websocket = self.active_connections[conversation_id]
            await websocket.send_json(message)

manager = ConnectionManager() 