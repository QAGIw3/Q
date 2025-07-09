import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal

from app.services.h2m_pulsar import h2m_pulsar_client
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

logger = logging.getLogger(__name__)
router = APIRouter()

class FeedbackRequest(BaseModel):
    message_id: str = Field(..., description="The unique ID of the message being rated.")
    conversation_id: Optional[str] = Field(None, description="The ID of the conversation the message belongs to.")
    feedback: Literal["good", "bad"] = Field(..., description="The user's feedback.")
    text: str = Field(..., description="The text of the message that received feedback.")

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_feedback(
    request: FeedbackRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Receives feedback from a user and publishes it to a Pulsar topic for later processing.
    """
    logger.info(f"Received '{request.feedback}' feedback from user '{user.username}' for message '{request.message_id}'.")
    
    feedback_data = request.dict()
    feedback_data['user'] = user.dict() # Add user info to the event payload

    try:
        await h2m_pulsar_client.send_feedback(feedback_data)
        return {"status": "Feedback received"}
    except RuntimeError as e:
        logger.error(f"Failed to send feedback to Pulsar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The feedback processing service is currently unavailable."
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred while processing feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred."
        ) 