import logging
import time
import threading
from typing import Optional

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.core.agent_registry import agent_registry
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.models import TaskStatus, WorkflowStatus

logger = logging.getLogger(__name__)

class WorkflowExecutor:
    """
    A background process that executes pending workflows.
    """

    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

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
        Fetches all running workflows and dispatches any tasks that are ready.
        """
        # Note: This is a simple implementation. A real system would need more
        # robust querying to avoid loading all active workflows into memory.
        # For example, querying for workflows with pending tasks.
        active_workflows = workflow_manager.get_all_running_workflows() # This method needs to be created
        
        for workflow in active_workflows:
            ready_tasks = workflow.get_ready_tasks()
            if not ready_tasks:
                continue

            logger.info(f"Found {len(ready_tasks)} ready tasks for workflow '{workflow.workflow_id}'.")
            for task in ready_tasks:
                agent = agent_registry.find_agent_by_prefix(task.agent_personality)
                if not agent:
                    logger.warning(f"No agent found for personality '{task.agent_personality}'. Task '{task.task_id}' will be deferred.")
                    continue
                
                # Check for and substitute results from dependencies
                prompt = self.substitute_dependencies(task.prompt, workflow)

                task_dispatcher.dispatch_task(
                    agent_id=agent['agent_id'],
                    prompt=prompt,
                    model="default", # Let the agent decide its model
                    task_id=task.task_id, # Pass the specific task_id
                    workflow_id=workflow.workflow_id # Pass the workflow_id for context
                )
                
                workflow_manager.update_task_status(workflow.workflow_id, task.task_id, TaskStatus.DISPATCHED)

    def substitute_dependencies(self, prompt: str, workflow: 'Workflow') -> str:
        """
        Replaces placeholders like {{task_1.result}} in a prompt with the actual
        results from completed dependency tasks.
        """
        import re
        
        def replacer(match):
            dependency_task_id = match.group(1)
            dependency_task = workflow.get_task(dependency_task_id)
            if dependency_task and dependency_task.status == TaskStatus.COMPLETED:
                return str(dependency_task.result)
            # If the dependency isn't met or has no result, leave the placeholder
            return match.group(0)

        return re.sub(r"\{\{([\w\d_-]+)\.result\}\}", replacer, prompt)

# Singleton instance
workflow_executor = WorkflowExecutor() 