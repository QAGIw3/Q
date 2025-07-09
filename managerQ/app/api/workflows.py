from fastapi import APIRouter, HTTPException, status, Body
from typing import List, Dict, Any

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.models import Workflow

router = APIRouter()

@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow_details(workflow_id: str):
    """Retrieves the full details of a specific workflow."""
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
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