from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
import logging

from app.models.inference import InferenceRequest
from app.core.pulsar_client import PulsarManager, get_pulsar_manager
from app.core.config import config
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

REQUEST_TOPIC = config.pulsar.topics.requests

@router.post("/v1/inference", status_code=status.HTTP_202_ACCEPTED)
async def create_inference_request(
    request: InferenceRequest,
    background_tasks: BackgroundTasks,
    pulsar_manager: PulsarManager = Depends(get_pulsar_manager),
    user: UserClaims = Depends(get_current_user)
):
    """
    Accepts an inference request and publishes it to the message queue for processing.
    """
    try:
        # Publishing to Pulsar can be an I/O operation.
        # For a truly async producer, the pulsar-client would need to be used with an async framework.
        # Here, we use a background task to avoid blocking the response.
        background_tasks.add_task(
            pulsar_manager.publish_request,
            topic=REQUEST_TOPIC,
            request=request
        )
        
        logger.info(f"Accepted inference request {request.request_id} from user '{user.username}'. Publishing to topic {REQUEST_TOPIC}.")

        return {
            "message": "Inference request accepted for processing.",
            "request_id": request.request_id
        }
    except ConnectionError as ce:
        logger.error(f"Pulsar connection error while handling request {request.request_id}: {ce}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The messaging service is currently unavailable."
        )
    except Exception as e:
        logger.error(f"Failed to process inference request {request.request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request."
        ) 