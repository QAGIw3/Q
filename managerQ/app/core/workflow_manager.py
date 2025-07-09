import logging
from typing import Optional, Dict, Any, List
from pyignite import Client
from pyignite.exceptions import PyIgniteError
from pyignite.queries.op_codes import OP_CACHE_GET_OR_CREATE_WITH_CONFIGURATION
from pyignite.datatypes import String, Bool, Int, Map, ObjectArray, Collection, prop_codes

from managerQ.app.models import Workflow, WorkflowStatus, TaskStatus
from managerQ.app.config import settings
from managerQ.app.api.dashboard_ws import manager as dashboard_manager
from managerQ.app.models import WorkflowTask

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
            
            # Define the schema for the 'workflows' cache, including an index on event_id
            schema = {
                'cache_name': 'workflows',
                'query_entities': [
                    {
                        'table_name': 'WORKFLOW',
                        'key_field_name': 'WORKFLOW_ID',
                        'key_type_name': 'java.lang.String',
                        'field_name_aliases': [],
                        'query_fields': [
                            {'name': 'WORKFLOW_ID', 'type_name': 'java.lang.String'},
                            {'name': 'EVENT_ID', 'type_name': 'java.lang.String'},
                            {'name': 'STATUS', 'type_name': 'java.lang.String'},
                            # Add other fields you want to query here
                        ],
                        'indexes': [
                            {'name': 'EVENT_ID_IDX', 'is_unique': False, 'fields': {'EVENT_ID': False}},
                            {'name': 'STATUS_IDX', 'is_unique': False, 'fields': {'STATUS': False}},
                        ],
                    },
                ],
            }
            
            self._cache = self._client.get_or_create_cache(schema)
            logger.info("WorkflowManager connected to Ignite and got or created cache 'workflows' with schema.")
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

    def start_workflow(self, workflow: Workflow):
        """
        Starts or resumes a workflow by calling the executor.
        This is a convenience method that might be the same as create for now,
        but could have different logic in the future (e.g., for resuming).
        """
        self.create_workflow(workflow)

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Retrieves a workflow from the cache."""
        workflow_data = self._cache.get(workflow_id)
        if workflow_data:
            return Workflow(**workflow_data)
        return None

    def get_workflow_by_event_id(self, event_id: str) -> Optional[Workflow]:
        """Retrieves a workflow from the cache using its event_id."""
        query = "SELECT * FROM Workflow WHERE event_id = ?"
        try:
            cursor = self._cache.sql(query, query_args=[event_id], include_field_names=False)
            row = next(cursor, None)
            if row:
                # Assuming the order of fields in the row matches the model
                # A more robust way is to use include_field_names=True and map by name
                return Workflow(**row)
            return None
        except PyIgniteError as e:
            logger.error(f"Failed to query for workflow by event_id '{event_id}': {e}", exc_info=True)
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

    def patch_workflow(self, workflow_id: str, failed_task_id: str, new_tasks: List[Dict[str, Any]]):
        """
        Inserts a list of new tasks into a workflow to correct a failure.
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow: return

        failed_task = workflow.get_task(failed_task_id)
        if not failed_task: return

        # 1. Find tasks that depended on the failed task
        downstream_tasks = [t for t in workflow.get_all_tasks_recursive() if failed_task_id in t.dependencies]

        # 2. Identify the last task(s) in the new corrective plan
        new_task_objects = [WorkflowTask(**t) for t in new_tasks]
        new_task_ids = {t.task_id for t in new_task_objects}
        final_new_task_ids = new_task_ids - {dep for t in new_task_objects for dep in t.dependencies}

        # 3. Rewire downstream tasks to depend on the new final task(s)
        for task in downstream_tasks:
            task.dependencies.remove(failed_task_id)
            task.dependencies.extend(list(final_new_task_ids))

        # 4. Set the first task in the new plan to depend on the failed task's dependencies
        if new_task_objects:
            first_new_task = new_task_objects[0] # Assuming ordered plan for now
            first_new_task.dependencies.extend(failed_task.dependencies)
        
        # 5. Add the new tasks to the workflow
        workflow.tasks.extend(new_task_objects)
        
        # Mark the failed task as "corrected" or a similar status if we add one.
        # For now, we leave it as FAILED.
        
        self.update_workflow(workflow)
        logger.info(f"Patched workflow '{workflow_id}' with {len(new_tasks)} new tasks.")

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