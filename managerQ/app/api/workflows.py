import logging
from fastapi import APIRouter, HTTPException, status, Body, Depends, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.models import Workflow, TaskStatus, ApprovalBlock, WorkflowStatus
from managerQ.app.core.goal_manager import goal_manager
from managerQ.app.core.goal import Goal
from managerQ.app.core.workflow_executor import workflow_executor
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from shared.observability.audit import audit_log

logger = logging.getLogger(__name__)
router = APIRouter()

class ApprovalRequest(BaseModel):
    approved: bool

class CreateWorkflowRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None

@router.get("/", response_model=List[Workflow])
async def list_workflows(
    status: Optional[WorkflowStatus] = Query(None, description="Filter workflows by status."),
    skip: int = Query(0, ge=0, description="Number of workflows to skip."),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of workflows to return.")
):
    """
    Retrieves a list of all workflows, with optional filtering and pagination.
    """
    all_workflows = workflow_manager.get_all_workflows()

    if status:
        filtered_workflows = [wf for wf in all_workflows if wf.status == status]
    else:
        filtered_workflows = all_workflows
    
    return filtered_workflows[skip : skip + limit]


@router.post("/", response_model=Workflow, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: CreateWorkflowRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Creates and starts a new workflow from a simple prompt.
    """
    try:
        # Create a high-level goal from the prompt
        new_goal = Goal(
            prompt=request.prompt,
            created_by=user.preferred_username,
            context=request.context or {}
        )
        goal_manager.create_goal(new_goal)

        audit_log("goal_created", user=user.preferred_username, details={"goal_id": new_goal.goal_id, "prompt": request.prompt})

        # Generate and run the workflow for this goal
        # In a real system, this might be asynchronous, but for an API we'll do it directly.
        workflow = await new_goal.create_and_run_workflow()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create a workflow from the provided prompt. The planning agent might have failed."
            )

        audit_log("workflow_created", user=user.preferred_username, details={"workflow_id": workflow.workflow_id, "from_goal": new_goal.goal_id})
        return workflow
    except Exception as e:
        # logger.error(f"Error creating workflow: {e}", exc_info=True) # Assuming logger is defined elsewhere
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )


@router.get("/by_event/{event_id}", response_model=Workflow)
async def get_workflow_by_event_id(event_id: str):
    """
    Retrieves a workflow by the event ID that triggered it.
    """
    # This is a conceptual implementation. The WorkflowManager would need
    # a way to index or efficiently query workflows by event_id.
    workflow = workflow_manager.get_workflow_by_event_id(event_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow for event ID '{event_id}' not found."
        )
    return workflow

@router.post("/{workflow_id}/tasks/{task_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_task(
    workflow_id: str,
    task_id: str,
    approval: ApprovalRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Sets the result of a task that is pending approval, checking for user authorization.
    """
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    task = workflow.get_task(task_id)
    if not isinstance(task, ApprovalBlock) or task.status != TaskStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Task is not an approval block or is not pending approval.")

    # RBAC Check
    if task.required_role and not user.has_role(task.required_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have the required role '{task.required_role}' to approve this task."
        )

    decision = "approved" if approval.approved else "rejected"
    
    audit_log(
        action="task_approval",
        user=user.preferred_username,
        details={
            "workflow_id": workflow_id,
            "task_id": task_id,
            "decision": decision
        }
    )

    if approval.approved:
        # If approved, mark as completed so the workflow can proceed
        workflow_manager.update_task_status(workflow_id, task_id, TaskStatus.COMPLETED, result=decision)
    else:
        # If rejected, mark as failed
        workflow_manager.update_task_status(workflow_id, task_id, TaskStatus.FAILED, result=decision)

    return


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow_by_id(workflow_id: str):
    """
    Retrieves the full state of a specific workflow by its ID.
    """
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found."
        )
    return workflow

@router.get("/{workflow_id}/context", response_model=Dict[str, Any])
async def get_workflow_context(workflow_id: str):
    """Retrieves the shared context of a specific workflow."""
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    return workflow.shared_context

@router.patch("/{workflow_id}/context", status_code=status.HTTP_204_NO_CONTENT)
async def update_workflow_context(workflow_id: str, updates: Dict[str, Any] = Body(...)):
    """Updates (merges) the shared context of a specific workflow."""
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    
    # Merge the updates into the existing context
    workflow.shared_context.update(updates)
    workflow_manager.update_workflow(workflow)
    return 

@router.get("/{workflow_id}/history", response_model=list)
async def get_workflow_history(workflow_id: str):
    """
    Retrieves the history of a specific workflow, including all tasks and their results.
    This is a simplified representation. A real implementation would need a more robust way to track history.
    """
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found."
        )
    
    # This is a placeholder. A real implementation would need to store and retrieve a rich history of events.
    # For now, we will return the tasks as the history.
    return workflow.tasks 

class ApprovalResponse(BaseModel):
    approved: bool

@router.post("/{workflow_id}/tasks/{task_id}/respond", status_code=status.HTTP_200_OK)
def respond_to_approval_task(
    workflow_id: str,
    task_id: str,
    response: ApprovalResponse,
    user: UserClaims = Depends(get_current_user)
):
    """
    Allows a user to respond to a pending approval task.
    """
    logger.info(f"User '{user.username}' responded to approval task '{task_id}' with decision: {'approved' if response.approved else 'rejected'}")
    
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
        
    task = workflow.get_task(task_id)
    if not task or not isinstance(task, ApprovalBlock) or task.status != TaskStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Task is not a pending approval.")
    
    # Enforce RBAC for the approval
    if task.required_roles:
        user_roles = set(user.roles)
        if not user_roles.intersection(task.required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have one of the required roles: {task.required_roles}"
            )

    # Update task status and result
    new_status = TaskStatus.COMPLETED if response.approved else TaskStatus.FAILED
    result = "approved" if response.approved else "rejected"
    
    workflow_manager.update_task_status(workflow_id, task_id, new_status, result)
    
    # Trigger the executor to process the next steps
    workflow_executor.process_workflow(workflow)
    
    return {"status": "Response recorded."} 