from fastapi import APIRouter, HTTPException, status
from typing import List

from managerQ.app.core.goal_manager import goal_manager
from managerQ.app.models import Goal, ClarificationResponse, Workflow
from managerQ.app.core.planner import planner, AmbiguousGoalError
from managerQ.app.core.workflow_manager import workflow_manager

router = APIRouter()

@router.post("", response_model=Goal, status_code=status.HTTP_201_CREATED)
async def create_goal(goal: Goal):
    """
    Creates a new long-term goal for the platform.
    """
    try:
        goal_manager.create_goal(goal)
        return goal
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("", response_model=List[Goal])
async def list_active_goals():
    """
    Lists all currently active goals.
    """
    try:
        return goal_manager.get_all_active_goals()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{goal_id}", response_model=Goal)
async def get_goal(goal_id: str):
    """
    Retrieves a specific goal by its ID.
    """
    goal = goal_manager.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    return goal

@router.post("/{workflow_id}/clarify", response_model=Workflow)
async def clarify_and_replan(workflow_id: str, response: ClarificationResponse):
    """
    Provides a clarification to an ambiguous goal and re-triggers the planning process.
    """
    # 1. Get the original workflow that is pending clarification
    original_workflow = workflow_manager.get_workflow(workflow_id)
    if not original_workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")

    # We might want to add a status to the workflow to check if it's actually 'PENDING_CLARIFICATION'

    try:
        # 2. Call the planner to create a new plan with the additional context
        new_workflow = await planner.replan_with_clarification(
            original_prompt=original_workflow.original_prompt,
            user_clarification=response.answer
        )

        # 3. Create the new workflow in the manager
        workflow_manager.create_workflow(new_workflow)

        # Optional: Update the old workflow's status to 'SUPERSEDED' or similar

        return new_workflow
    except AmbiguousGoalError as e:
        # If it's still ambiguous, the user needs to try again.
        # This requires saving the clarification attempt state. For now, we raise an error.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Goal is still ambiguous: {e.clarifying_question}"}
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 