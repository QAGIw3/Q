import logging
import time
import threading
from typing import Optional, List, Set
import jinja2
import json

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.core.agent_registry import agent_registry
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.models import TaskStatus, WorkflowStatus, Workflow, TaskBlock, WorkflowTask, ConditionalBlock, ApprovalBlock, WorkflowEvent
from managerQ.app.api.dashboard_ws import broadcast_workflow_event
import asyncio
import pulsar
from managerQ.app.config import settings

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
        self._pulsar_client: pulsar.Client = None
        self._task_producer: pulsar.Producer = None
        self._conditional_producer: pulsar.Producer = None
        # Initialize Jinja2 environment for condition evaluation
        self._jinja_env = jinja2.Environment()

    def start(self):
        """Starts the executor loop in a background thread."""
        if self._running:
            logger.warning("WorkflowExecutor is already running.")
            return
            
        self._pulsar_client = pulsar.Client(settings.pulsar.service_url)
        self._task_producer = self._pulsar_client.create_producer(settings.pulsar.topics.tasks_dispatch)
        self._conditional_producer = self._pulsar_client.create_producer(settings.pulsar.topics.tasks_conditional)

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"WorkflowExecutor started with a poll interval of {self.poll_interval}s.")

    def stop(self):
        """Stops the executor loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._task_producer:
            self._task_producer.close()
        if self._conditional_producer:
            self._conditional_producer.close()
        if self._pulsar_client:
            self._pulsar_client.close()
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
                
                # Broadcast completion event
                asyncio.run(broadcast_workflow_event(WorkflowEvent(
                    event_type="WORKFLOW_COMPLETED",
                    workflow_id=workflow.workflow_id,
                    data={"status": final_status.value}
                )))

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
            
            elif isinstance(block, ApprovalBlock):
                self._handle_approval_block(block, workflow)

    def _handle_approval_block(self, block: ApprovalBlock, workflow: Workflow):
        """Handles a workflow block that requires human approval."""
        logger.info(f"Pausing workflow '{workflow.workflow_id}' for human approval on task '{block.task_id}'.")
        
        # Update the task's status to indicate it's waiting for a decision.
        # The workflow will not proceed down this path until an external API call
        # changes this status to 'COMPLETED' (approved) or 'FAILED' (rejected).
        workflow_manager.update_task_status(workflow.workflow_id, block.task_id, TaskStatus.PENDING_APPROVAL)
        
        # Broadcast the event so the UI can update
        asyncio.run(broadcast_workflow_event(WorkflowEvent(
            event_type="APPROVAL_REQUIRED",
            workflow_id=workflow.workflow_id,
            task_id=block.task_id,
            data={"message": block.message}
        )))

    def _dispatch_task(self, task: WorkflowTask, workflow: Workflow):
        """Renders a task's prompt and dispatches it to an agent."""
        logger.info(f"Dispatching task '{task.task_id}' for workflow '{workflow.workflow_id}' to Pulsar.")
        
        try:
            # Render prompt using Jinja2 and the workflow's shared context
            template = self._jinja_env.from_string(task.prompt)
            rendered_prompt = template.render(workflow.shared_context)
            
            task_payload = {
                "task_id": task.task_id,
                "workflow_id": workflow.workflow_id,
                "agent_personality": task.agent_personality,
                "prompt": rendered_prompt,
            }
            
            self._task_producer.send(json.dumps(task_payload).encode('utf-8'))
            
            workflow_manager.update_task_status(workflow.workflow_id, task.task_id, TaskStatus.DISPATCHED)
            
            # Broadcast dispatch event
            asyncio.run(broadcast_workflow_event(WorkflowEvent(
                event_type="TASK_STATUS_UPDATE",
                workflow_id=workflow.workflow_id,
                task_id=task.task_id,
                data={"status": TaskStatus.DISPATCHED.value}
            )))

        except jinja2.TemplateError as e:
            logger.error(f"Failed to render prompt for task '{task.task_id}': {e}", exc_info=True)
            workflow_manager.update_task_status(workflow.workflow_id, task.task_id, TaskStatus.FAILED, result=f"Prompt rendering failed: {e}")
        except Exception as e:
            logger.error(f"Failed to publish task '{task.task_id}' to Pulsar: {e}", exc_info=True)
            # Optionally, set the task to FAILED here as well
            workflow_manager.update_task_status(workflow.workflow_id, task.task_id, TaskStatus.FAILED, result="Failed to publish to message queue.")


    def _evaluate_conditional(self, block: ConditionalBlock, workflow: Workflow):
        """Publishes a conditional evaluation task to Pulsar."""
        logger.info(f"Publishing conditional evaluation for block '{block.task_id}' to Pulsar.")
        
        conditional_payload = {
            "block_id": block.task_id,
            "workflow_id": workflow.workflow_id,
        }
        
        self._conditional_producer.send(json.dumps(conditional_payload).encode('utf-8'))
        
        # We don't mark as complete here anymore. The worker will do that.
        # We can, however, mark it as "evaluating" if we add such a status.
        # For now, we'll leave it as PENDING until the worker picks it up.

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