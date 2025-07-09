from fastapi import APIRouter, HTTPException, status, Depends
import logging
from pydantic import BaseModel

from managerQ.app.core.planner import planner, AmbiguousGoalError
from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.models import Workflow, WorkflowStatus, TaskBlock
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

logger = logging.getLogger(__name__)
router = APIRouter()

class TaskRequest(BaseModel):
    prompt: str

class WorkflowSubmitResponse(BaseModel):
    workflow_id: str
    status: str
    num_tasks: int
    clarifying_question: str = None

@router.post("", response_model=WorkflowSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_task_and_create_workflow(
    request: TaskRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Accepts a user prompt, uses the Planner to create a workflow,
    and then either dispatches it directly (for single-task workflows)
    or saves it for the WorkflowExecutor to run.
    """
    try:
        # 1. Use the Planner to decompose the prompt into a workflow
        workflow = await planner.create_plan(request.prompt)
        
        # 2. If it's a simple, single-task plan, dispatch it directly
        if len(workflow.tasks) == 1 and not workflow.tasks[0].dependencies:
            task = workflow.tasks[0]
            logger.info("Dispatching single-task workflow directly.", workflow_id=workflow.workflow_id)
            task_dispatcher.dispatch_task(
                prompt=task.prompt,
                agent_id=None, # Let the dispatcher find a suitable agent
                task_id=task.task_id,
                workflow_id=workflow.workflow_id
            )
            return WorkflowSubmitResponse(
                workflow_id=workflow.workflow_id,
                status="Dispatched as single task.",
                num_tasks=1
            )

        # 3. For multi-step workflows, save them for the executor
        else:
            logger.info(f"Saving multi-step workflow '{workflow.workflow_id}' for asynchronous execution.")
            workflow_manager.create_workflow(workflow)
            return WorkflowSubmitResponse(
                workflow_id=workflow.workflow_id,
                status="Workflow accepted for execution.",
                num_tasks=len(workflow.tasks)
            )

    except AmbiguousGoalError as e:
        logger.warning(f"Ambiguous goal from user '{user.preferred_username}'. Creating workflow pending clarification.")
        
        # Create a placeholder workflow that is waiting for the user's response
        pending_workflow = Workflow(
            original_prompt=request.prompt,
            status=WorkflowStatus.PENDING_CLARIFICATION,
            tasks=[], # No tasks yet
            shared_context={
                "clarifying_question": e.clarifying_question
            }
        )
        workflow_manager.create_workflow(pending_workflow)

        return WorkflowSubmitResponse(
            workflow_id=pending_workflow.workflow_id,
            status=WorkflowStatus.PENDING_CLARIFICATION,
            num_tasks=0,
            clarifying_question=e.clarifying_question
        )

    except ValueError as e: # From planner failure
        logger.error(f"Planning failed for prompt '{request.prompt}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create a valid workflow: {e}")
    except RuntimeError as e: # From task dispatch failure
        logger.error(f"Task dispatch failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating workflow: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.") 