# managerQ/app/api/user_workflows.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from managerQ.app.models import Workflow
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from managerQ.app.core.user_workflow_store import user_workflow_store
from managerQ.app.core.workflow_manager import workflow_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("", response_model=Workflow)
async def create_user_workflow(
    workflow: Workflow,
    user: UserClaims = Depends(get_current_user)
):
    """Saves a new user-defined workflow."""
    # Associate the workflow with the user who created it
    workflow.shared_context['owner_id'] = user.user_id
    logger.info(f"User '{user.username}' is creating a new workflow: {workflow.workflow_id}")
    await user_workflow_store.save_workflow(workflow)
    return workflow

@router.get("/{workflow_id}", response_model=Workflow)
async def get_user_workflow(
    workflow_id: str,
    user: UserClaims = Depends(get_current_user)
):
    """Retrieves a specific user-defined workflow."""
    workflow = await user_workflow_store.get_workflow(workflow_id)
    if not workflow or workflow.shared_context.get('owner_id') != user.user_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.get("", response_model=List[Workflow])
async def list_user_workflows(
    user: UserClaims = Depends(get_current_user)
):
    """Lists all workflows owned by the current user."""
    return await user_workflow_store.get_workflows_by_owner(user.user_id)

@router.put("/{workflow_id}", response_model=Workflow)
async def update_user_workflow(
    workflow_id: str,
    workflow_data: Workflow,
    user: UserClaims = Depends(get_current_user)
):
    """Updates an existing workflow."""
    existing_workflow = await user_workflow_store.get_workflow(workflow_id)
    if not existing_workflow or existing_workflow.shared_context.get('owner_id') != user.user_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Ensure the owner isn't changed
    workflow_data.shared_context['owner_id'] = user.user_id
    await user_workflow_store.save_workflow(workflow_data)
    return workflow_data

@router.post("/{workflow_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_user_workflow(
    workflow_id: str,
    user: UserClaims = Depends(get_current_user)
):
    """
    Retrieves a user-defined workflow and starts its execution.
    """
    workflow = await user_workflow_store.get_workflow(workflow_id)
    if not workflow or workflow.shared_context.get('owner_id') != user.user_id:
        raise HTTPException(status_code=404, detail="Workflow not found or not owned by user.")
    
    logger.info(f"User '{user.username}' is running workflow '{workflow_id}'.")
    
    workflow_manager.start_workflow(workflow)
    
    return {"message": "Workflow execution started.", "workflow_id": workflow_id}

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_workflow(
    workflow_id: str,
    user: UserClaims = Depends(get_current_user)
):
    """Deletes a user-defined workflow."""
    await user_workflow_store.delete_workflow(workflow_id, user.user_id) 