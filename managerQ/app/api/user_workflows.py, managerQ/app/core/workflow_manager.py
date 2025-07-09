from managerQ.app.core.workflow_manager import workflow_manager

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
    
    # The workflow_manager handles the execution logic
    workflow_manager.start_workflow(workflow)
    
    return {"message": "Workflow execution started.", "workflow_id": workflow_id}

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT) 