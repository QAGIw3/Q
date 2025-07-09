import logging
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
import asyncio
import uuid

from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.core.result_listener import result_listener
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

logger = logging.getLogger(__name__)
router = APIRouter()

class AgentTaskRequest(BaseModel):
    agent_personality: str
    prompt: str

class AgentTaskResponse(BaseModel):
    result: str
    task_id: str

@router.post("", response_model=AgentTaskResponse)
async def delegate_task_to_agent(
    request: AgentTaskRequest,
    user: UserClaims = Depends(get_current_user) # Using user auth for now
):
    """
    Accepts a delegated task from another agent, dispatches it,
    and waits for the result.
    """
    task_id = str(uuid.uuid4())
    logger.info(
        "Received delegated task",
        task_id=task_id,
        target_personality=request.agent_personality,
        from_user=user.username
    )

    try:
        # Create a future to wait for the result
        result_future = asyncio.Future()
        result_listener.add_future(task_id, result_future)

        # Dispatch the task to the appropriate agent
        task_dispatcher.dispatch_task(
            prompt=request.prompt,
            agent_personality=request.agent_personality,
            task_id=task_id
        )

        # Wait for the result_listener to set the future's result
        result = await asyncio.wait_for(result_future, timeout=300.0) # 5-minute timeout

        return AgentTaskResponse(result=result, task_id=task_id)

    except asyncio.TimeoutError:
        logger.error(f"Delegated task {task_id} timed out.")
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="The delegated task timed out.")
    except RuntimeError as e:
        logger.error(f"Failed to dispatch delegated task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    finally:
        # Clean up the future from the listener
        result_listener.remove_future(task_id) 