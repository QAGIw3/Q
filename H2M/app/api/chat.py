import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
import asyncio

from app.core.orchestrator import orchestrator
from app.core.connection_manager import manager
from app.core.human_feedback import human_feedback_listener
from app.services.h2m_pulsar import h2m_pulsar_client
from shared.q_auth_parser.parser import get_user_claims_ws
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
    claims: UserClaims = Depends(get_user_claims_ws)
):
    # The initial connection does not have a conversation_id yet.
    # We will use a temporary one until the first message is processed.
    temp_connection_id = ""
    
    try:
        # The first message from the client must contain the conversation_id
        # or be a new conversation.
        initial_data = await websocket.receive_json()
        request = ChatRequest(**initial_data)
        
        user_id = claims.sub
        current_conversation_id = request.conversation_id

        # Handle the very first message to get a stable conversation_id
        ai_response, conv_id = await orchestrator.handle_message(
            user_id=user_id,
            text=request.text,
            conversation_id=current_conversation_id
        )
        
        # Now we have a stable ID, register the connection
        await manager.connect(conv_id, websocket)
        temp_connection_id = conv_id

        # Send the first response
        await manager.send_to_conversation(conv_id, {"text": ai_response, "conversation_id": conv_id})

        while True:
            data = await websocket.receive_json()
            request = ChatRequest(**data)
            
            # If this message is a response from the human to the agent
            if request.is_human_response:
                await h2m_pulsar_client.send_human_response(
                    conversation_id=conv_id,
                    response_text=request.text
                )
                # We don't need a response from the orchestrator in this case
                continue

            # Otherwise, it's a normal chat message
            ai_response, conv_id = await orchestrator.handle_message(
                user_id=user_id,
                text=request.text,
                conversation_id=conv_id # Use the established conv_id
            )
            await manager.send_to_conversation(conv_id, {"text": ai_response, "conversation_id": conv_id})

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed for conversation: {temp_connection_id}")
        manager.disconnect(temp_connection_id)
    except Exception as e:
        logger.error(f"An error occurred in the WebSocket for conversation {temp_connection_id}: {e}", exc_info=True)
        manager.disconnect(temp_connection_id)
        await websocket.close(code=1011, reason=f"An internal error occurred.") 