from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import uuid

class TaskStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4()}")
    agent_personality: str = Field(description="The type of agent needed, e.g., 'default', 'devops'.")
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = Field(default_factory=list, description="List of task_ids that must be completed before this one can start.")
    result: Optional[str] = None

class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Workflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4()}")
    original_prompt: str
    status: WorkflowStatus = WorkflowStatus.RUNNING
    tasks: List[WorkflowTask]
    shared_context: Dict[str, Any] = Field(default_factory=dict, description="A shared dictionary for agents in this workflow to read/write intermediate results.")
    
    def get_task(self, task_id: str) -> Optional[WorkflowTask]:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_ready_tasks(self) -> List[WorkflowTask]:
        """Returns a list of tasks whose dependencies are met."""
        ready_tasks = []
        completed_task_ids = {
            task.task_id for task in self.tasks if task.status == TaskStatus.COMPLETED
        }
        for task in self.tasks:
            if task.status == TaskStatus.PENDING and set(task.dependencies).issubset(completed_task_ids):
                ready_tasks.append(task)
        return ready_tasks

# --- Goal Models ---

class Condition(BaseModel):
    metric: str = Field(description="The name of the metric to monitor, e.g., 'cpu_usage', 'error_rate'.")
    operator: Literal["<", ">", "==", "!=", "<=", ">="]
    value: float
    service: str = Field(description="The service the metric applies to.")

class Goal(BaseModel):
    goal_id: str = Field(default_factory=lambda: f"goal_{uuid.uuid4()}")
    objective: str = Field(..., description="A high-level description of the desired state.")
    is_active: bool = True
    conditions: List[Condition] = Field(..., description="A list of conditions that define the goal.")
    remediation_workflow_id: Optional[str] = Field(None, description="The ID of a specific workflow to trigger if this goal is breached.") 