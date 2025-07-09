from fastapi import APIRouter, HTTPException, status, Body, Depends
from typing import List, Dict, Any
from pydantic import BaseModel

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.models import Workflow, TaskStatus, ApprovalBlock
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from shared.observability.audit import audit_log

router = APIRouter()

class ApprovalRequest(BaseModel):
    approved: bool

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