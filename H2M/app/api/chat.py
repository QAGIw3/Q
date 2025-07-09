import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
import asyncio
import uuid

from app.core.orchestrator import orchestrator
from app.core.connection_manager import manager
from app.core.human_feedback import human_feedback_listener
from app.services.h2m_pulsar import h2m_pulsar_client
from shared.q_auth_parser.parser import get_current_user_ws
from shared.q_auth_parser.models import UserClaims

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    text: str
    conversation_id: str | None = None
    is_human_response: bool = False # Flag to indicate this is a reply to an agent

async def forward_agent_question(conversation_id: str, data: dict):
    """Callback function for the HumanFeedbackListener."""
    await manager.send_to_conversation(conversation_id, data)

# Set the callback on the listener instance
if human_feedback_listener:
    human_feedback_listener.forward_to_user_callback = forward_agent_question

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user: UserClaims = Depends(get_current_user_ws)
):
    # This connection is now long-lived for a given user, but not tied to a single conversation
    await manager.connect(user.sub, websocket) # Use user ID as a temporary key
    
    current_conversation_id: str | None = None
    
    try:
        while True:
            data = await websocket.receive_json()
            request = ChatRequest(**data)
            
            # The first message from the client will establish the conversation_id for this session
            if not current_conversation_id:
                current_conversation_id = request.conversation_id or str(uuid.uuid4())
                # Re-key the connection with the stable conversation_id
                manager.re_key_connection(user.sub, current_conversation_id, websocket)

            # If this message is a response from the human to the agent
            if request.is_human_response:
                await h2m_pulsar_client.send_human_response(
                    conversation_id=current_conversation_id,
                    response_text=request.text
                )
                continue

            # Otherwise, it's a normal chat message, start the streaming process
            async for chunk in orchestrator.handle_message_stream(
                user_id=user.user_id,
                text=request.text,
                conversation_id=current_conversation_id
            ):
                await manager.send_to_conversation(current_conversation_id, chunk)

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed for conversation: {current_conversation_id or user.sub}")
        manager.disconnect(current_conversation_id or user.sub)
    except Exception as e:
        logger.error(f"An error occurred in the WebSocket for conversation {current_conversation_id or user.sub}: {e}", exc_info=True)
        manager.disconnect(current_conversation_id or user.sub)
        # Don't try to close an already closed socket
        # await websocket.close(code=1011, reason=f"An internal error occurred.") 