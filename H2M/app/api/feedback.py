import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.services.h2m_pulsar import h2m_pulsar_client
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from app.h2m_models import FeedbackEvent

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_feedback(
    request: FeedbackEvent,
    user: UserClaims = Depends(get_current_user)
):
    """
    Receives feedback from a user and publishes it to a Pulsar topic for later processing.
    """
    logger.info(f"Received feedback from user '{user.username}' for item '{request.reference_id}' in context '{request.context}'. Score: {request.score}")
    
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