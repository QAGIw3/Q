import logging
import pulsar
import fastavro
import io
from typing import Dict, Any, Optional
import uuid
from datetime import datetime
from collections import defaultdict

from managerQ.app.core.agent_registry import agent_registry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Avro schema for the prompt messages, must match agentQ's schema
PROMPT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.managerq", "type": "record", "name": "PromptMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "model", "type": "string"},
        {"name": "timestamp", "type": "long"},
        # New fields for workflow context
        {"name": "workflow_id", "type": ["null", "string"], "default": None},
        {"name": "task_id", "type": ["null", "string"], "default": None},
    ]
})

class TaskDispatcher:
    """
    Selects agents and dispatches tasks via Pulsar.
    Also tracks pending tasks for different personalities.
    """

    def __init__(self, service_url: str, task_topic_prefix: str):
        self._service_url = service_url
        self._task_topic_prefix = task_topic_prefix
        self._client: Optional[pulsar.Client] = None
        self._producers: Dict[str, pulsar.Producer] = {}
        # A dictionary to track the number of pending tasks per agent personality
        self.pending_tasks: Dict[str, int] = defaultdict(int)

    def start(self):
        """Initializes the Pulsar client."""
        self._client = pulsar.Client(self._service_url)
        logger.info("TaskDispatcher started.")

    def stop(self):
        """Closes all cached producers and the client."""
        for producer in self._producers.values():
            producer.close()
        if self._client:
            self._client.close()
        logger.info("TaskDispatcher stopped.")

    def _get_producer(self, topic: str) -> pulsar.Producer:
        """Gets or creates a producer for a given agent's task topic."""
        if topic not in self._producers:
            logger.info(f"Creating new producer for topic: {topic}")
            self._producers[topic] = self._client.create_producer(
                topic,
                schema=pulsar.schema.BytesSchema()
            )
        return self._producers[topic]

    def dispatch_task(
        self,
        prompt: str,
        agent_id: Optional[str] = None,
        agent_personality: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        model: str = "default"
    ) -> str:
        """
        Selects an agent and dispatches a task.
        An agent can be selected by specific ID or by personality.
        """
        if not agent_registry:
            raise RuntimeError("AgentRegistry not initialized.")

        agent = None
        if agent_id:
            agent = agent_registry.get_agent_by_id(agent_id)
        elif agent_personality:
            agent = agent_registry.find_agent_by_prefix(agent_personality)
        
        if not agent:
            raise RuntimeError(f"No available agent found for dispatch. Requested ID: {agent_id}, Personality: {agent_personality}")

        final_agent_id = agent["agent_id"]
        task_topic = agent["task_topic"]
        
        message_id = task_id or str(uuid.uuid4())

        task_data = {
            "id": message_id,
            "prompt": prompt,
            "model": model,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "workflow_id": workflow_id,
            "task_id": task_id
        }
        
        logger.info(
            "Dispatching task to agent", 
            task_id=message_id, 
            agent_id=final_agent_id, 
            workflow_id=workflow_id
        )

        try:
            producer = self._get_producer(task_topic)
            buf = io.BytesIO()
            fastavro.writer(buf, PROMPT_SCHEMA, [task_data])
            producer.send(buf.getvalue())
            self.pending_tasks[agent_personality] += 1
            logger.info(f"Dispatched task {task_id} to agent {final_agent_id}. Pending tasks for '{agent_personality}': {self.pending_tasks[agent_personality]}")

            return final_agent_id
        except Exception as e:
            logger.error(f"Failed to dispatch task to agent {final_agent_id}: {e}", exc_info=True)
            raise

    def decrement_pending_tasks(self, agent_personality: str):
        """Decrements the pending task count for a given personality."""
        if self.pending_tasks[agent_personality] > 0:
            self.pending_tasks[agent_personality] -= 1
        logger.info(f"Completed task for '{agent_personality}'. Pending tasks: {self.pending_tasks[agent_personality]}")


# Global instance
task_dispatcher: Optional[TaskDispatcher] = None 