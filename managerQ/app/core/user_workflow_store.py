# managerQ/app/core/user_workflow_store.py
import logging
from typing import List, Optional

from pyignite import AioClient
from pyignite.exceptions import PyIgniteError

from managerQ.app.models import Workflow
from managerQ.app.config import settings

logger = logging.getLogger(__name__)

USER_WORKFLOWS_CACHE_NAME = "user_workflows"

class UserWorkflowStore:
    def __init__(self):
        self._client = AioClient()

    async def connect(self):
        if not self._client.is_connected():
            await self._client.connect(settings.ignite.addresses)
            await self._client.get_or_create_cache(USER_WORKFLOWS_CACHE_NAME)
            logger.info("Connected to Ignite and ensured user_workflows cache exists.")

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        cache = await self._client.get_cache(USER_WORKFLOWS_CACHE_NAME)
        workflow_dict = await cache.get(workflow_id)
        return Workflow(**workflow_dict) if workflow_dict else None

    async def save_workflow(self, workflow: Workflow):
        cache = await self._client.get_cache(USER_WORKFLOWS_CACHE_NAME)
        await cache.put(workflow.workflow_id, workflow.dict())

    async def get_workflows_by_owner(self, owner_id: str) -> List[Workflow]:
        # This is inefficient as it requires a full table scan.
        # A real implementation would use a SQL query with a secondary index on owner_id.
        cache = await self._client.get_cache(USER_WORKFLOWS_CACHE_NAME)
        workflows = []
        cursor = await cache.scan()
        for _, workflow_dict in cursor:
            if workflow_dict.get("shared_context", {}).get("owner_id") == owner_id:
                workflows.append(Workflow(**workflow_dict))
        return workflows

    async def delete_workflow(self, workflow_id: str, owner_id: str):
        # Ensure the user owns the workflow before deleting
        workflow = await self.get_workflow(workflow_id)
        if workflow and workflow.shared_context.get('owner_id') == owner_id:
            cache = await self._client.get_cache(USER_WORKFLOWS_CACHE_NAME)
            await cache.remove_key(workflow_id)
            logger.info(f"Deleted workflow '{workflow_id}' for user '{owner_id}'.")

# Singleton instance
user_workflow_store = UserWorkflowStore() 