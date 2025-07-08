import logging
import pulsar
import fastavro
import io
from typing import Dict, Any, Optional

from managerQ.app.core.agent_registry import agent_registry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Avro schema for the prompt messages, must match agentQ's schema
PROMPT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.h2m", "type": "record", "name": "PromptMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "model", "type": "string"}, # Can be used to request a specific model type
        {"name": "timestamp", "type": "long"}
    ]
})

class TaskDispatcher:
    """
    Dispatches tasks to available agentQ workers.
    """

    def __init__(self, service_url: str):
        self._service_url = service_url
        self._client: Optional[pulsar.Client] = None
        # Cache producers for each agent's task topic
        self._producers: Dict[str, pulsar.Producer] = {}

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

    def dispatch_task(self, task_data: Dict[str, Any]) -> str:
        """
        Selects an agent and dispatches a task to it.
        
        Args:
            task_data: A dictionary representing the task to be sent.
            
        Returns:
            The agent_id that the task was dispatched to.
            
        Raises:
            RuntimeError: If no agents are available.
        """
        if not agent_registry:
            raise RuntimeError("AgentRegistry not initialized.")

        agent = agent_registry.get_agent()
        if not agent:
            raise RuntimeError("No available agents to dispatch task.")

        agent_id = agent["agent_id"]
        task_topic = agent["task_topic"]
        
        logger.info(f"Dispatching task {task_data['id']} to agent {agent_id} on topic {task_topic}")

        try:
            producer = self._get_producer(task_topic)
            buf = io.BytesIO()
            fastavro.writer(buf, PROMPT_SCHEMA, [task_data])
            producer.send(buf.getvalue())
            return agent_id
        except Exception as e:
            logger.error(f"Failed to dispatch task to agent {agent_id}: {e}", exc_info=True)
            raise

# Global instance
task_dispatcher: Optional[TaskDispatcher] = None 