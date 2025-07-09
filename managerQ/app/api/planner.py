# managerQ/app/api/planner.py
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.models import Workflow
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

logger = logging.getLogger(__name__)
router = APIRouter()

class PlanRequest(BaseModel):
    goal: str

@router.post("/plan", response_model=Workflow, status_code=status.HTTP_201_CREATED)
async def create_plan_from_goal(
    request: PlanRequest,
    user: UserClaims = Depends(get_current_user)
):
    """
    Accepts a high-level goal, uses the planner_agent to generate a workflow,
    and starts the workflow.
    """
    logger.info(f"Received planning request from user '{user.username}': '{request.goal}'")
    
    try:
        # Dispatch the goal to the planner agent and wait for the plan
        task_id = task_dispatcher.dispatch_task(
            prompt=request.goal,
            agent_personality="planner_agent"
        )
        plan_json_str = await task_dispatcher.await_task_result(task_id, timeout=60)
        
        # Parse the plan and create the workflow
        plan_data = json.loads(plan_json_str)
        workflow = Workflow(**plan_data)
        
        workflow_manager.create_workflow(workflow)
        logger.info(f"Successfully created and started workflow '{workflow.workflow_id}' from plan.")
        
        return workflow

    except TimeoutError:
        raise HTTPException(status_code=504, detail="Planning agent timed out.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Planner agent returned invalid JSON.")
    except Exception as e:
        logger.error(f"Failed to create plan from goal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create plan.") 