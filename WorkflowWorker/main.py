import logging
import json
import pulsar
import threading
import time
from typing import Optional
import jinja2

# This worker will need access to some of the managerQ's components
# In a real-world scenario, these would be shared libraries.
from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.core.agent_registry import agent_registry
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.models import TaskStatus, Workflow, ConditionalBlock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WorkflowWorker")

class Worker:
    def __init__(self, service_url: str, task_topic: str, conditional_topic: str):
        self._service_url = service_url
        self._task_topic = task_topic
        self._conditional_topic = conditional_topic
        self._client: Optional[pulsar.Client] = None
        self._task_consumer: Optional[pulsar.Consumer] = None
        self._conditional_consumer: Optional[pulsar.Consumer] = None
        self._running = False
        self._jinja_env = jinja2.Environment()

    def start(self):
        if self._running:
            return
        
        self._client = pulsar.Client(self._service_url)
        
        # Consumer for agent tasks
        self._task_consumer = self._client.subscribe(
            self._task_topic,
            subscription_name="workflow-worker-tasks-sub",
            consumer_type=pulsar.ConsumerType.Shared
        )
        
        # Consumer for conditional evaluations
        self._conditional_consumer = self._client.subscribe(
            self._conditional_topic,
            subscription_name="workflow-worker-conditionals-sub",
            consumer_type=pulsar.ConsumerType.Shared
        )
        
        self._running = True
        
        # Run consumers in separate threads
        threading.Thread(target=self._run_consumer, args=(self._task_consumer, self.handle_task_message), daemon=True).start()
        threading.Thread(target=self._run_consumer, args=(self._conditional_consumer, self.handle_conditional_message), daemon=True).start()
        
        logger.info("WorkflowWorker started.")

    def stop(self):
        self._running = False
        # The threads will exit gracefully
        if self._client:
            self._client.close()
        logger.info("WorkflowWorker stopped.")

    def _run_consumer(self, consumer, handler):
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

    def handle_task_message(self, msg):
        """Handles a message to dispatch an agent task."""
        payload = json.loads(msg.data().decode('utf-8'))
        logger.info(f"Received agent task: {payload['task_id']}")
        
        # This logic is moved from the original WorkflowExecutor._dispatch_task
        agent = agent_registry.find_agent_by_prefix(payload['agent_personality'])
        if not agent:
            # Handle error - maybe publish to a failed tasks topic
            logger.error(f"No agent found for personality: {payload['agent_personality']}")
            return
            
        task_dispatcher.dispatch_task(
            agent_id=agent['agent_id'],
            prompt=payload['prompt'],
            task_id=payload['task_id'],
            workflow_id=payload['workflow_id']
        )
        logger.info(f"Dispatched task {payload['task_id']} to agent {agent['agent_id']}")

    def handle_conditional_message(self, msg):
        """Handles a message to evaluate a conditional block."""
        payload = json.loads(msg.data().decode('utf-8'))
        workflow_id = payload['workflow_id']
        block_id = payload['block_id']
        
        logger.info(f"Evaluating conditional block '{block_id}' in workflow '{workflow_id}'.")
        
        workflow = workflow_manager.get_workflow(workflow_id)
        if not workflow:
            logger.error(f"Workflow '{workflow_id}' not found for conditional evaluation.")
            return
            
        block = workflow.get_task(block_id)
        if not isinstance(block, ConditionalBlock):
            logger.error(f"Block '{block_id}' is not a ConditionalBlock.")
            return

        context = self._get_evaluation_context(workflow)

        for branch in block.branches:
            try:
                template = self._jinja_env.from_string(branch.condition)
                if template.render(context).lower() in ['true', '1', 'yes']:
                    logger.info(f"Condition '{branch.condition}' for block '{block_id}' is TRUE.")
                    workflow_manager.update_task_status(workflow_id, block_id, TaskStatus.COMPLETED)
                    # The WorkflowExecutor will pick up the newly available tasks in the branch on its next run.
                    return
            except Exception as e:
                logger.error(f"Failed to evaluate condition '{branch.condition}' for block '{block_id}': {e}", exc_info=True)
                workflow_manager.update_task_status(workflow_id, block_id, TaskStatus.FAILED, result=f"Condition evaluation failed: {e}")
                return

        # No conditions were met
        logger.info(f"No conditions met for block '{block_id}'.")
        workflow_manager.update_task_status(workflow_id, block_id, TaskStatus.COMPLETED)

    def _get_evaluation_context(self, workflow: Workflow) -> dict:
        """Creates a context for Jinja2 rendering from the workflow state."""
        context = workflow.shared_context.copy()
        task_results = {}
        for task in workflow.get_all_tasks_recursive():
            if task.status == TaskStatus.COMPLETED:
                try:
                    task_results[task.task_id] = json.loads(task.result) if task.result and task.result.strip().startswith(('{', '[')) else task.result
                except (json.JSONDecodeError, TypeError):
                    task_results[task.task_id] = task.result
        context['tasks'] = task_results
        return context


if __name__ == "__main__":
    # In a real app, this would come from config
    SERVICE_URL = "pulsar://localhost:6650"
    TASK_TOPIC = "persistent://public/default/q.tasks.dispatch"
    CONDITIONAL_TOPIC = "persistent://public/default/q.tasks.conditional"
    
    worker = Worker(SERVICE_URL, TASK_TOPIC, CONDITIONAL_TOPIC)
    worker.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.stop() 