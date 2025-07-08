from fastapi import APIRouter, HTTPException, status
import logging
import uuid
import time

from pydantic import BaseModel
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.core.result_listener import result_listener

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter()

class TaskRequest(BaseModel):
    prompt: str
    model: str = "default"

class TaskResponse(BaseModel):
    task_id: str
    agent_id: str
    result: str
    llm_model: str

@router.post("", response_model=TaskResponse)
async def submit_task(request: TaskRequest):
    """
    Submits a task to an available agent and waits for the result.
    """
    if not task_dispatcher or not result_listener:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ManagerQ components are not initialized."
        )

    task_id = str(uuid.uuid4())
    task_data = {
        "id": task_id,
        "prompt": request.prompt,
        "model": request.model,
        "timestamp": int(time.time() * 1000)
    }

    try:
        # 1. Dispatch the task to an available agent
        agent_id = task_dispatcher.dispatch_task(task_data)
        
        # 2. Wait for the result to come back
        result_data = await result_listener.get_result(task_id, timeout=60) # 60-second timeout

        return TaskResponse(
            task_id=task_id,
            agent_id=agent_id,
            result=result_data.get("result"),
            llm_model=result_data.get("llm_model")
        )

    except RuntimeError as e:
        logger.error(f"Task dispatch failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except TimeoutError as e:
        logger.error(f"Task timed out: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred while processing task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.") 