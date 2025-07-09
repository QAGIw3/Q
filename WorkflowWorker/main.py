import logging
import json
import pulsar
import threading
import time
from typing import Optional, Dict, Any
import jinja2
from opentelemetry import trace, context as trace_context

from shared.pulsar_tracing import extract_trace_context, inject_trace_context
from shared.opentelemetry.tracing import setup_tracing
from .config import settings

# from managerQ.app.core.workflow_manager import workflow_manager # Decoupling
# from managerQ.app.core.agent_registry import agent_registry # Decoupling
# from managerQ.app.core.task_dispatcher import task_dispatcher # Decoupling
from managerQ.app.models import TaskStatus # Keep for enum, will be moved to shared lib

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("WorkflowWorker")
setup_tracing(service_name="WorkflowWorker")
tracer = trace.get_tracer(__name__)


class Worker:
    def __init__(self):
        self._client: Optional[pulsar.Client] = None
        self._task_consumer: Optional[pulsar.Consumer] = None
        self._conditional_consumer: Optional[pulsar.Consumer] = None
        self._status_update_producer: Optional[pulsar.Producer] = None
        self._running = False
        self._jinja_env = jinja2.Environment()

    def start(self):
        if self._running:
            return
        
        logger.info("Starting WorkflowWorker...")
        self._client = pulsar.Client(settings.PULSAR_SERVICE_URL)
        
        dead_letter_policy = pulsar.DeadLetterPolicy(
            max_redeliver_count=settings.MAX_REDELIVER_COUNT,
            dead_letter_topic=settings.DEAD_LETTER_TOPIC
        )

        # Consumer for agent tasks
        self._task_consumer = self._client.subscribe(
            settings.AGENT_TASK_TOPIC,
            subscription_name=settings.AGENT_TASK_SUBSCRIPTION,
            consumer_type=pulsar.ConsumerType.Shared,
            dead_letter_policy=dead_letter_policy
        )
        
        # Consumer for conditional evaluations
        self._conditional_consumer = self._client.subscribe(
            settings.CONDITIONAL_TOPIC,
            subscription_name=settings.CONDITIONAL_SUBSCRIPTION,
            consumer_type=pulsar.ConsumerType.Shared,
            dead_letter_policy=dead_letter_policy
        )

        # Producer for task status updates
        self._status_update_producer = self._client.create_producer(
            settings.TASK_STATUS_UPDATE_TOPIC
        )
        
        self._running = True
        
        # Run consumers in separate threads
        threading.Thread(target=self._run_consumer, args=(self._task_consumer, self.handle_task_message), daemon=True).start()
        threading.Thread(target=self._run_consumer, args=(self._conditional_consumer, self.handle_conditional_message), daemon=True).start()
        
        logger.info("WorkflowWorker started successfully.")

    def stop(self):
        self._running = False
        logger.info("Stopping WorkflowWorker...")
        if self._task_consumer:
            self._task_consumer.close()
        if self._conditional_consumer:
            self._conditional_consumer.close()
        if self._status_update_producer:
            self._status_update_producer.close()
        if self._client:
            self._client.close()
        logger.info("WorkflowWorker stopped.")

    def _run_consumer(self, consumer: pulsar.Consumer, handler):
        while self._running:
            try:
                msg = consumer.receive(timeout_millis=1000)
                handler(msg)
                consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                if 'msg' in locals():
                    consumer.negative_acknowledge(msg)
                time.sleep(5)

    def _publish_status_update(self, workflow_id: str, task_id: str, status: TaskStatus, result: Optional[Any] = None):
        """Publishes a task status update message."""
        update_payload = {
            "workflow_id": workflow_id,
            "task_id": task_id,
            "status": status.value,
            "result": result,
            "source": "WorkflowWorker"
        }
        
        headers = {}
        inject_trace_context(headers)

        self._status_update_producer.send(
            json.dumps(update_payload).encode('utf-8'),
            properties=headers
        )
        logger.info(f"Published status update for task {task_id}: {status.value}")


    def handle_task_message(self, msg: pulsar.Message):
        """Handles a message to dispatch an agent task."""
        try:
            payload = json.loads(msg.data().decode('utf-8'))
            task_id = payload['task_id']
            workflow_id = payload['workflow_id']
            logger.info(f"Received agent task: {task_id}")
            
            context = extract_trace_context(msg.properties())
            with tracer.start_as_current_span("handle_agent_task", context=context) as span:
                span.set_attributes({
                    "workflow_id": workflow_id,
                    "task_id": task_id
                })

                # TODO: Replace direct agent_registry and task_dispatcher calls
                # For now, we assume this worker's job is to orchestrate, not execute.
                # It finds an agent and tells another system (via Pulsar) to run it.
                # This part needs to be redesigned. For now, we'll simulate the dispatch
                # and just publish a status update.

                # In a decoupled world, this might call an Agent "runner" service
                # or the logic would be here.
                # agent = agent_registry.find_agent_by_prefix(payload['agent_personality'])
                agent_personality = payload.get('agent_personality')
                if not agent_personality:
                    logger.error(f"Task {task_id} is missing 'agent_personality'.")
                    self._publish_status_update(workflow_id, task_id, TaskStatus.FAILED, result="Missing 'agent_personality' in payload")
                    return

                # SIMULATION: In the future, this would dispatch to another service.
                # For now, we'll just mark it as "running" as its been "dispatched"
                # by this worker.
                logger.info(f"Task {task_id} requires agent '{agent_personality}'. Simulating dispatch.")
                self._publish_status_update(workflow_id, task_id, TaskStatus.RUNNING)

        except Exception as e:
            logger.error(f"Failed to process task message: {e}", exc_info=True)
            # This will trigger the dead-letter policy after max retries
            raise

    def handle_conditional_message(self, msg: pulsar.Message):
        """Handles a message to evaluate a conditional block."""
        try:
            payload = json.loads(msg.data().decode('utf-8'))
            workflow_id = payload['workflow_id']
            block_id = payload['block_id']
            
            context = extract_trace_context(msg.properties())
            with tracer.start_as_current_span("handle_conditional_evaluation", context=context) as span:
                span.set_attributes({
                    "workflow_id": workflow_id,
                    "block_id": block_id
                })
                logger.info(f"Evaluating conditional block '{block_id}' in workflow '{workflow_id}'.")
                
                # To fully decouple, the workflow state should be passed in the message
                # or fetched from a shared state store like Ignite/Redis.
                # For now, we'll assume the necessary context is in the payload.
                eval_context = payload.get('evaluation_context', {})
                branches = payload.get('branches', [])

                if not eval_context or not branches:
                    logger.error(f"Missing 'evaluation_context' or 'branches' for conditional '{block_id}'.")
                    self._publish_status_update(workflow_id, block_id, TaskStatus.FAILED, result="Missing data for conditional evaluation.")
                    return

                for branch in branches:
                    try:
                        condition = branch.get('condition')
                        if not condition:
                            continue
                        template = self._jinja_env.from_string(condition)
                        # The context for rendering now comes from the message payload
                        if template.render(eval_context).lower() in ['true', '1', 'yes']:
                            logger.info(f"Condition '{condition}' for block '{block_id}' is TRUE. Next step is '{branch.get('next_task')}'")
                            # The result of a conditional is which branch was taken.
                            self._publish_status_update(workflow_id, block_id, TaskStatus.COMPLETED, result={"branch_taken": branch.get('next_task')})
                            return
                    except Exception as e:
                        logger.error(f"Failed to evaluate condition '{condition}' for block '{block_id}': {e}", exc_info=True)
                        self._publish_status_update(workflow_id, block_id, TaskStatus.FAILED, result=f"Condition evaluation failed: {e}")
                        return

                # No conditions were met
                logger.info(f"No conditions met for block '{block_id}'.")
                self._publish_status_update(workflow_id, block_id, TaskStatus.COMPLETED, result={"branch_taken": None})

        except Exception as e:
            logger.error(f"Failed to process conditional message: {e}", exc_info=True)
            # This will trigger the dead-letter policy after max retries
            raise

    def _get_evaluation_context(self, workflow: Any) -> dict:
        # This function is now deprecated in favor of receiving context via message.
        # It will be removed in a future commit.
        return {}


if __name__ == "__main__":
    worker = Worker()
    worker.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.stop() 