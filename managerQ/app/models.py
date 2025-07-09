from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal, Union
from enum import Enum
import uuid

class TaskStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4()}")
    type: Literal["task"] = "task"
    agent_personality: str = Field(description="The type of agent needed, e.g., 'default', 'devops'.")
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = Field(default_factory=list, description="List of task_ids that must be completed before this one can start.")
    result: Optional[str] = None

# --- NEW: Models for Conditional Logic ---

class ConditionalBranch(BaseModel):
    """A branch of tasks to be executed if a condition is met."""
    condition: str = Field(description="A Jinja2-like condition to evaluate against the workflow's shared_context, e.g., '{{ task_1.result.status }} == \"success\"'")
    tasks: List['TaskBlock'] = Field(default_factory=list, description="A list of tasks to execute if the condition is true.")

class ConditionalBlock(BaseModel):
    """A block that allows for conditional execution paths in a workflow."""
    task_id: str = Field(default_factory=lambda: f"cond_{uuid.uuid4()}")
    type: Literal["conditional"] = "conditional"
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = Field(default_factory=list, description="List of task_ids that must be completed before this conditional block can be evaluated.")
    branches: List[ConditionalBranch]

# A Union type representing any execution block in the workflow graph.
TaskBlock = Union[WorkflowTask, ConditionalBlock]

# Update Pydantic's forward references to handle the recursive TaskBlock definition.
ConditionalBranch.update_forward_refs(TaskBlock=TaskBlock)


class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Workflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4()}")
    original_prompt: str
    status: WorkflowStatus = WorkflowStatus.RUNNING
    tasks: List[TaskBlock]
    shared_context: Dict[str, Any] = Field(default_factory=dict, description="A shared dictionary for agents in this workflow to read/write intermediate results.")
    
    def get_task(self, task_id: str) -> Optional[TaskBlock]:
        """Recursively finds a task or block by its ID."""
        def find_task_recursive(search_id: str, blocks: List[TaskBlock]) -> Optional[TaskBlock]:
            for block in blocks:
                if block.task_id == search_id:
                    return block
                if isinstance(block, ConditionalBlock):
                    for branch in block.branches:
                        found = find_task_recursive(search_id, branch.tasks)
                        if found:
                            return found
            return None
        return find_task_recursive(task_id, self.tasks)

    def get_all_tasks_recursive(self) -> List[TaskBlock]:
        """Returns a flattened list of all tasks and blocks in the workflow."""
        all_blocks = []
        def gather_blocks(blocks: List[TaskBlock]):
            for block in blocks:
                all_blocks.append(block)
                if isinstance(block, ConditionalBlock):
                    for branch in block.branches:
                        gather_blocks(branch.tasks)
        gather_blocks(self.tasks)
        return all_blocks

    def get_ready_tasks(self) -> List[TaskBlock]:
        """
        Returns a list of tasks or blocks whose dependencies are met.
        NOTE: This implementation is now more complex and tightly coupled with the executor's logic.
        The executor will need to handle the recursive nature of the workflow.
        """
        all_blocks = self.get_all_tasks_recursive()
        completed_task_ids = {
            block.task_id for block in all_blocks if block.status == TaskStatus.COMPLETED
        }
        
        ready_tasks = []
        for task in all_blocks:
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