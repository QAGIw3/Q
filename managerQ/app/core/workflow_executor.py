import logging
import time
import threading
from typing import Optional, List, Set
import jinja2
import json

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.core.agent_registry import agent_registry
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.models import TaskStatus, WorkflowStatus, Workflow, TaskBlock, WorkflowTask, ConditionalBlock

logger = logging.getLogger(__name__)

class WorkflowExecutor:
    """
    A background process that executes pending workflows, supporting complex
    conditional logic and nested tasks.
    """

    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # Initialize Jinja2 environment for condition evaluation
        self._jinja_env = jinja2.Environment()

    def start(self):
        """Starts the executor loop in a background thread."""
        if self._running:
            logger.warning("WorkflowExecutor is already running.")
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"WorkflowExecutor started with a poll interval of {self.poll_interval}s.")

    def stop(self):
        """Stops the executor loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        logger.info("WorkflowExecutor stopped.")

    def _run_loop(self):
        """The main loop for processing active workflows."""
        while self._running:
            try:
                self.process_active_workflows()
            except Exception as e:
                logger.error(f"Error in WorkflowExecutor loop: {e}", exc_info=True)
            
            time.sleep(self.poll_interval)

    def process_active_workflows(self):
        """
        Fetches all running workflows and processes their execution state.
        """
        active_workflows = workflow_manager.get_all_running_workflows()
        
        for workflow in active_workflows:
            # This is a terminal state, so we won't process it further here.
            if workflow.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                continue

            self._process_blocks(workflow.tasks, workflow)

            # After processing, check if the entire workflow has reached a terminal state
            all_blocks_after = workflow.get_all_tasks_recursive() # Re-fetch after processing
            is_complete = all(block.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] for block in all_blocks_after)
            
            if is_complete:
                # Determine final status: FAILED if any task failed, otherwise COMPLETED
                final_status = WorkflowStatus.FAILED if any(b.status == TaskStatus.FAILED for b in all_blocks_after) else WorkflowStatus.COMPLETED
                workflow.status = final_status
                workflow_manager.update_workflow(workflow)
                logger.info(f"Workflow '{workflow.workflow_id}' has finished with status '{final_status.value}'.")
                
                # Trigger the reflection task
                self._trigger_reflection_task(workflow)

    def _trigger_reflection_task(self, workflow: Workflow):
        """Creates and dispatches a task for a 'reflector' agent to analyze a completed workflow."""
        logger.info(f"Triggering reflection for workflow '{workflow.workflow_id}'.")
        
        # Serialize the workflow to JSON to pass to the reflector
        workflow_dump = workflow.json(indent=2)

        prompt = (
            "You are a Reflector Agent. Your purpose is to analyze a completed workflow to find insights and lessons.\n\n"
            "Analyze the following workflow execution record. Identify key successes, failures, and reasons for the outcome. "
            "Formulate a concise 'lesson learned' that can be stored in our knowledge graph to improve future planning.\n\n"
            f"Workflow Analysis Request for: {workflow.workflow_id}\n"
            f"Original Goal: {workflow.original_prompt}\n"
            f"Final Status: {workflow.status.value}\n\n"
            f"Full Workflow Record:\n{workflow_dump}"
        )

        try:
            # Dispatch to a reflector agent. This is a "fire-and-forget" task.
            task_dispatcher.dispatch_task(
                prompt=prompt,
                agent_personality='reflector'
            )
            logger.info(f"Successfully dispatched reflection task for workflow '{workflow.workflow_id}'.")
        except RuntimeError as e:
            logger.error(f"Failed to dispatch reflection task for workflow '{workflow.workflow_id}': {e}", exc_info=True)


    def _process_blocks(self, blocks: List[TaskBlock], workflow: Workflow):
        """Recursively processes a list of tasks or conditional blocks."""
        # Get all completed task IDs *once* for the current processing cycle.
        all_blocks = workflow.get_all_tasks_recursive()
        completed_ids = {block.task_id for block in all_blocks if block.status == TaskStatus.COMPLETED}

        for block in blocks:
            # Skip blocks that are not ready or already processed
            if block.status != TaskStatus.PENDING or not set(block.dependencies).issubset(completed_ids):
                continue

            # Process based on block type
            if isinstance(block, WorkflowTask):
                self._dispatch_task(block, workflow)
            
            elif isinstance(block, ConditionalBlock):
                self._evaluate_conditional(block, workflow)

    def _dispatch_task(self, task: WorkflowTask, workflow: Workflow):
        """Renders a task's prompt and dispatches it to an agent."""
        logger.info(f"Dispatching task '{task.task_id}' for workflow '{workflow.workflow_id}'.")
        agent = agent_registry.find_agent_by_prefix(task.agent_personality)
        if not agent:
            logger.warning(f"No agent for personality '{task.agent_personality}'. Task '{task.task_id}' deferred.")
            return

        try:
            # Render prompt using Jinja2 and the workflow's shared context
            template = self._jinja_env.from_string(task.prompt)
            rendered_prompt = template.render(workflow.shared_context)
        except jinja2.TemplateError as e:
            logger.error(f"Failed to render prompt for task '{task.task_id}': {e}", exc_info=True)
            # Mark task as failed
            workflow_manager.update_task_status(workflow.workflow_id, task.task_id, TaskStatus.FAILED, result=f"Prompt rendering failed: {e}")
            return
            
        task_dispatcher.dispatch_task(
            agent_id=agent['agent_id'],
            prompt=rendered_prompt,
            task_id=task.task_id,
            workflow_id=workflow.workflow_id
        )
        
        workflow_manager.update_task_status(workflow.workflow_id, task.task_id, TaskStatus.DISPATCHED)

    def _evaluate_conditional(self, block: ConditionalBlock, workflow: Workflow):
        """Evaluates the branches of a conditional block."""
        logger.debug(f"Evaluating conditional block '{block.task_id}' in workflow '{workflow.workflow_id}'.")
        
        # Once a conditional's dependencies are met, we evaluate its branches.
        # The block's status will be updated to COMPLETED if a branch is taken,
        # or if no branch condition is met.

        for branch in block.branches:
            try:
                template = self._jinja_env.from_string(branch.condition)
                context = self._get_evaluation_context(workflow)
                
                if template.render(context).lower() in ['true', '1', 'yes']:
                    logger.info(f"Condition '{branch.condition}' for block '{block.task_id}' evaluated to True. Processing branch.")
                    # Mark the conditional block itself as completed *before* processing the new branch
                    workflow_manager.update_task_status(workflow.workflow_id, block.task_id, TaskStatus.COMPLETED)
                    # Recursively process the tasks in the chosen branch
                    self._process_blocks(branch.tasks, workflow)
                    return # Exit after finding the first true branch
            except jinja2.TemplateError as e:
                logger.error(f"Failed to evaluate condition '{branch.condition}' for block '{block.task_id}': {e}", exc_info=True)
                workflow_manager.update_task_status(workflow.workflow_id, block.task_id, TaskStatus.FAILED, result=f"Condition rendering failed: {e}")
                return # Stop processing this conditional if a condition is malformed

        # If no branch was taken, the conditional is considered complete.
        logger.debug(f"No conditions met for conditional block '{block.task_id}'. Marking as complete.")
        workflow_manager.update_task_status(workflow.workflow_id, block.task_id, TaskStatus.COMPLETED)

    def _get_evaluation_context(self, workflow: Workflow) -> dict:
        """
        Creates a context for Jinja2 rendering, combining workflow's shared_context
        with the results of all completed tasks.
        """
        context = workflow.shared_context.copy()
        
        # Add task results to the context under a 'tasks' key for easy access.
        # e.g., {{ tasks.task_1.result }}
        task_results = {}
        for task in workflow.get_all_tasks_recursive():
            if task.status == TaskStatus.COMPLETED and isinstance(task, WorkflowTask):
                 # Try to parse JSON result, otherwise use the raw string
                try:
                    task_results[task.task_id] = json.loads(task.result) if task.result and task.result.strip().startswith(('{', '[')) else task.result
                except (json.JSONDecodeError, TypeError):
                    task_results[task.task_id] = task.result

        context['tasks'] = task_results
        return context

# Singleton instance
workflow_executor = WorkflowExecutor() 