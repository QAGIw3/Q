import logging
from typing import Optional, Dict, Any
from pyignite import Client
from pyignite.exceptions import PyIgniteError

from managerQ.app.models import Workflow, WorkflowStatus, TaskStatus
from managerQ.app.config import settings
from managerQ.app.api.dashboard_ws import manager as dashboard_manager

logger = logging.getLogger(__name__)

class WorkflowManager:
    """
    Manages the lifecycle of workflows in an Ignite cache.
    """

    def __init__(self):
        self._client = Client()
        self._cache = None
        self.connect()

    def connect(self):
        try:
            self._client.connect(settings.ignite.addresses)
            self._cache = self._client.get_or_create_cache("workflows")
            logger.info("WorkflowManager connected to Ignite and got cache 'workflows'.")
        except PyIgniteError as e:
            logger.error(f"Failed to connect WorkflowManager to Ignite: {e}", exc_info=True)
            raise

    def close(self):
        if self._client.is_connected():
            self._client.close()

    def create_workflow(self, workflow: Workflow) -> None:
        """Saves a new workflow to the cache."""
        logger.info(f"Creating workflow: {workflow.workflow_id}")
        self._cache.put(workflow.workflow_id, workflow.dict())

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Retrieves a workflow from the cache."""
        workflow_data = self._cache.get(workflow_id)
        if workflow_data:
            return Workflow(**workflow_data)
        return None

    def update_task_status(
        self,
        workflow_id: str,
        task_id: str,
        status: TaskStatus,
        result: Optional[str] = None,
        context_updates: Optional[Dict[str, Any]] = None
    ):
        """Updates the status and result of a specific task and merges data into the shared context."""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            logger.error(f"Cannot update task: Workflow '{workflow_id}' not found.")
            return

        task = workflow.get_task(task_id)
        if not task:
            logger.error(f"Cannot update task: Task '{task_id}' not found in workflow '{workflow_id}'.")
            return
            
        task.status = status
        if result:
            task.result = result
        
        # Merge new data into the shared context
        if context_updates:
            workflow.shared_context.update(context_updates)

        self.update_workflow(workflow)

        # Broadcast the update to the dashboard
        dashboard_manager.broadcast({
            "event_type": "workflow_task_updated",
            "data": {
                "workflow_id": workflow_id,
                "task_id": task_id,
                "status": status,
                "result": result
            }
        })

    def update_workflow(self, workflow: Workflow) -> None:
        """Saves the entire state of a workflow back to the cache."""
        # The value must be a dict to be compatible with Ignite's SQL engine
        self._cache.put(workflow.workflow_id, workflow.dict())
        logger.debug(f"Updated workflow: {workflow.workflow_id}")

    def get_all_running_workflows(self) -> list[Workflow]:
        """Retrieves all workflows with status 'RUNNING' using a SQL query."""
        query = f"SELECT * FROM Workflow WHERE status = '{WorkflowStatus.RUNNING.value}'"
        try:
            # The result of a SQL query is an iterable cursor
            cursor = self._cache.sql(query, include_field_names=False)
            workflows = [Workflow(**row) for row in cursor]
            if workflows:
                logger.info(f"Found {len(workflows)} running workflows.")
            return workflows
        except PyIgniteError as e:
            logger.error(f"Failed to query for running workflows: {e}", exc_info=True)
            return []

# Singleton instance for use across the application
workflow_manager = WorkflowManager() 