from fastapi import APIRouter, HTTPException, status
from typing import List

from managerQ.app.core.goal_manager import goal_manager
from managerQ.app.models import Goal

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