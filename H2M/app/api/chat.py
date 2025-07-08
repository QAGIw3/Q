import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel

from app.core.orchestrator import orchestrator
from shared.q_auth_parser.parser import get_user_claims
from shared.q_auth_parser.models import UserClaims

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    text: str
    conversation_id: str | None = None

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # This is a simplified auth flow for WebSockets.
    # A robust implementation would handle the token in the initial connection handshake.
    # For now, we assume a secure connection is established.
    await websocket.accept()
    logger.info("WebSocket connection established.")
    
    try:
        while True:
            # Receive a message from the client
            data = await websocket.receive_json()
            request = ChatRequest(**data)
            
            logger.info(f"Received message for conversation: {request.conversation_id}")
            
            # Use the orchestrator to handle the message and get a response
            ai_response, conv_id = await orchestrator.handle_message(
                text=request.text,
                conversation_id=request.conversation_id
            )
            
            # Stream the response back to the client
            response_data = {
                "text": ai_response,
                "conversation_id": conv_id
            }
            await websocket.send_json(response_data)
            logger.info(f"Sent response for conversation: {conv_id}")

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed.")
    except Exception as e:
        logger.error(f"An error occurred in the WebSocket endpoint: {e}", exc_info=True)
        # Attempt to send an error message before closing
        await websocket.close(code=1011, reason=f"An internal error occurred: {e}") 