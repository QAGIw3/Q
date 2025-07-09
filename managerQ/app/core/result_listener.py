import logging
import pulsar
import fastavro
import io
import threading
import time
import asyncio
import json
from typing import Dict, Any, Optional

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.models import TaskStatus
from managerQ.app.models import WorkflowEvent
from managerQ.app.api.dashboard_ws import broadcast_workflow_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Avro schema for the result messages, must match agentQ's schema
RESULT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ResultMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "result", "type": "string"},
        {"name": "llm_model", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "timestamp", "type": "long"},
        # New fields for workflow context
        {"name": "workflow_id", "type": ["null", "string"], "default": None},
        {"name": "task_id", "type": ["null", "string"], "default": None},
        {"name": "agent_personality", "type": ["null", "string"], "default": None},
    ]
})

class ResultListener:
    """
    Listens for results from agentQ workers.
    It can update workflow state or fulfill a future for a delegated task.
    """

    def __init__(self, service_url: str, results_topic: str):
        self._service_url = service_url
        self._results_topic = results_topic
        self._client: Optional[pulsar.Client] = None
        self._consumer: Optional[pulsar.Consumer] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # For handling delegated tasks synchronously
        self._futures: Dict[str, asyncio.Future] = {}

    def add_future(self, task_id: str, future: asyncio.Future):
        """Adds a future to the listener's tracking dictionary."""
        self._futures[task_id] = future

    def remove_future(self, task_id: str):
        """Removes a future from the dictionary, typically after completion or timeout."""
        if task_id in self._futures:
            del self._futures[task_id]

    def start(self):
        """Starts the result listener in a background thread."""
        if self._running:
            return
            
        self._client = pulsar.Client(self._service_url)
        self._consumer = self._client.subscribe(
            self._results_topic,
            subscription_name="managerq-results-sub",
            subscription_type=pulsar.SubscriptionType.Shared
        )
        
        self._running = True
        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info("ResultListener started in background thread.")

    def stop(self):
        """Stops the result listener."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._client:
            self._client.close()
        logger.info("ResultListener stopped.")

    def _run_consumer(self):
        """The main loop for consuming result messages."""
        while self._running:
            try:
                msg = self._consumer.receive(timeout_millis=1000)
                bytes_reader = io.BytesIO(msg.data())
                result_data = next(fastavro.reader(bytes_reader, RESULT_SCHEMA), None)
                
                self.handle_result(result_data)
                
                self._consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in ResultListener consumer loop: {e}", exc_info=True)
                if 'msg' in locals():
                    self._consumer.negative_acknowledge(msg)
                time.sleep(5)

    def handle_result(self, result_data: Dict[str, Any]):
        """
        Processes a result message.
        If it's for a delegated task, it fulfills the future.
        If it's part of a workflow, it updates the workflow state.
        """
        if not result_data:
            return

        task_id = result_data.get("task_id") or result_data.get("id")
        workflow_id = result_data.get("workflow_id")
        result_text = result_data.get("result")
        agent_personality = result_data.get("agent_personality")

        # Set the result for any part of the system that might be awaiting it
        if task_id:
            task_dispatcher.set_task_result(task_id, result_text)

        # Decrement pending task count for the personality
        if agent_personality:
            task_dispatcher.decrement_pending_tasks(agent_personality)

        # Check if this result corresponds to a delegated task waiting for a response
        if task_id and task_id in self._futures:
            future = self._futures[task_id]
            if not future.done():
                future.set_result(result_text)
            logger.info(f"Fulfilled future for delegated task {task_id}.")
            # We don't remove the future here; the calling endpoint is responsible for cleanup.
            return # Stop processing, as this was a simple delegation

        # If not a delegated task, check if it's part of a larger workflow
        if workflow_id and task_id:
            logger.info(
                "Received result for workflow task", 
                workflow_id=workflow_id, 
                task_id=task_id
            )

            # Try to parse the result string as JSON to allow for structured data passing
            try:
                result_data_json = json.loads(result_text)
            except json.JSONDecodeError:
                result_data_json = result_text # Keep as string if not valid JSON

            # The context update is keyed by the task_id for easy access in templates
            context_updates = {
                task_id: {
                    "result": result_data_json
                }
            }
            
            # Broadcast the completion event
            asyncio.run(broadcast_workflow_event(WorkflowEvent(
                event_type="TASK_STATUS_UPDATE",
                workflow_id=workflow_id,
                task_id=task_id,
                data={"status": TaskStatus.COMPLETED.value, "result": result_text}
            )))

            workflow_manager.update_task_status(
                workflow_id=workflow_id,
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=result_text,
                context_updates=context_updates
            )
        else:
            # This is a result for a simple, non-workflow task that wasn't delegated.
            # We can log it or handle it differently if needed.
            logger.info(f"Received standalone result for task: {result_data.get('id')}")

# Global instance
result_listener: Optional[ResultListener] = None 