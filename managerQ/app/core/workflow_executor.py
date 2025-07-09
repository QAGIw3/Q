import logging
import threading
from typing import Optional, List, Set
import jinja2
import json
from datetime import datetime

from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.models import TaskStatus, WorkflowStatus, Workflow, TaskBlock, WorkflowTask, ConditionalBlock, ApprovalBlock, WorkflowEvent
from managerQ.app.api.dashboard_ws import broadcast_workflow_event
import asyncio
import pulsar
from managerQ.app.config import settings
from shared.pulsar_tracing import inject_trace_context, extract_trace_context
from opentelemetry import trace
from shared.observability.metrics import WORKFLOW_COMPLETED_COUNTER, WORKFLOW_DURATION_HISTOGRAM, TASK_COMPLETED_COUNTER
from managerQ.app.dependencies import get_kg_client # Import the dependency provider

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class WorkflowExecutor:
    """
    An event-driven process that listens for task status changes and advances
    workflows accordingly.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pulsar_client: pulsar.Client = None
        self._task_producer: pulsar.Producer = None
        self._conditional_producer: pulsar.Producer = None
        self._status_consumer: pulsar.Consumer = None
        self._jinja_env = jinja2.Environment()

    def start(self):
        """Starts the executor in a background thread to listen for events."""
        if self._running:
            logger.warning("WorkflowExecutor is already running.")
            return
            
        self._pulsar_client = pulsar.Client(settings.pulsar.service_url)
        self._task_producer = self._pulsar_client.create_producer(settings.pulsar.topics.tasks_dispatch)
        self._conditional_producer = self._pulsar_client.create_producer(settings.pulsar.topics.tasks_conditional)

        # Subscribe to the task status update topic
        self._status_consumer = self._pulsar_client.subscribe(
            settings.pulsar.topics.tasks_status_update,
            subscription_name="managerq-workflow-executor-status-sub",
            consumer_type=pulsar.ConsumerType.Shared
        )

        self._running = True
        self._thread = threading.Thread(target=self._consumer_loop, daemon=True)
        self._thread.start()
        logger.info("WorkflowExecutor started and is now listening for task status updates.")

    def stop(self):
        """Stops the executor loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._task_producer:
            self._task_producer.close()
        if self._conditional_producer:
            self._conditional_producer.close()
        if self._status_consumer:
            self._status_consumer.close()
        if self._pulsar_client:
            self._pulsar_client.close()
        logger.info("WorkflowExecutor stopped.")

    def _consumer_loop(self):
        """The main loop for consuming task status updates."""
        while self._running:
            try:
                msg = self._status_consumer.receive(timeout_millis=1000)
                self._handle_status_update(msg)
                self._status_consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in WorkflowExecutor consumer loop: {e}", exc_info=True)
                if 'msg' in locals():
                    self._status_consumer.negative_acknowledge(msg)
                asyncio.sleep(5)

    def _handle_status_update(self, msg: pulsar.Message):
        """Processes a task status update message and triggers workflow progression."""
        context = extract_trace_context(msg.properties())
        with tracer.start_as_current_span("handle_status_update", context=context) as span:
            payload = json.loads(msg.data().decode('utf-8'))
            workflow_id = payload.get("workflow_id")
            task_id = payload.get("task_id")
            status_str = payload.get("status")
            result = payload.get("result")

            if not all([workflow_id, task_id, status_str]):
                logger.error(f"Invalid status update message received: {payload}")
                return

            span.set_attributes({
                "workflow_id": workflow_id,
                "task_id": task_id,
                "status": status_str
            })
            logger.info(f"Received status update for task {task_id}: {status_str}")

            try:
                status = TaskStatus(status_str) if status_str else None
            except ValueError:
                logger.error(f"Invalid status '{status_str}' for task {task_id}.")
                return

            # Instrument task status metric
            if status and status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                TASK_COMPLETED_COUNTER.labels(status=status.value).inc()

            workflow_manager.update_task_status(workflow_id, task_id, status, result)

            workflow = workflow_manager.get_workflow(workflow_id)
            if workflow and workflow.status == WorkflowStatus.RUNNING:
                self.process_workflow(workflow)

    def process_workflow(self, workflow: Workflow):
        """
        Processes a single workflow's execution state, dispatching any new tasks that are ready.
        """
        logger.info(f"Processing workflow '{workflow.workflow_id}'...")
        self._process_blocks(workflow.tasks, workflow)

        all_blocks_after = workflow.get_all_tasks_recursive()
        is_complete = all(block.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED} for block in all_blocks_after)
        
        if is_complete:
            final_status = WorkflowStatus.FAILED if any(b.status == TaskStatus.FAILED for b in all_blocks_after) else WorkflowStatus.COMPLETED
            
            # Instrument workflow metrics
            WORKFLOW_COMPLETED_COUNTER.labels(status=final_status.value).inc()
            duration_seconds = time.time() - workflow.created_at.timestamp()
            WORKFLOW_DURATION_HISTOGRAM.observe(duration_seconds)

            workflow.status = final_status
            workflow_manager.update_workflow(workflow)
            logger.info(f"Workflow '{workflow.workflow_id}' has finished with status '{final_status.value}'.")
            
            asyncio.run(broadcast_workflow_event(WorkflowEvent(
                event_type="WORKFLOW_COMPLETED",
                workflow_id=workflow.workflow_id,
                data={"status": final_status.value}
            )))
            
            # Check if this was an AIOps workflow and handle the final report
            if workflow.event_id and final_status == WorkflowStatus.COMPLETED:
                self._handle_completed_aiops_workflow(workflow)
            else:
                self._trigger_reflection_task(workflow)

    def _handle_completed_aiops_workflow(self, workflow: Workflow):
        """
        Handles the completion of a event-driven workflow, like the AIOps one,
        by ingesting the final report into the Knowledge Graph.
        """
        logger.info(f"Handling completed AIOps workflow '{workflow.workflow_id}'.")
        
        # Find the final task (a task with no other tasks depending on it)
        all_task_ids = {task.task_id for task in workflow.get_all_tasks_recursive()}
        dependency_ids = set()
        for task in workflow.get_all_tasks_recursive():
            dependency_ids.update(task.dependencies)
            
        final_task_ids = all_task_ids - dependency_ids
        
        if not final_task_ids:
            logger.warning(f"Could not determine final task for AIOps workflow '{workflow.workflow_id}'.")
            return
            
        # Assuming one final report task for simplicity
        final_task_id = final_task_ids.pop()
        final_task = workflow.get_task(final_task_id)
        
        if not final_task or not final_task.result:
            logger.warning(f"Final task '{final_task_id}' for AIOps workflow has no result to ingest.")
            return
            
        service_name = workflow.shared_context.get("service_name")
        if not service_name:
            logger.warning("AIOps workflow is missing 'service_name' in shared_context.")
            return

        logger.info(f"Ingesting final report from task '{final_task_id}' into Knowledge Graph.")
        
        try:
            # This is not ideal, but a workaround for the client management issue
            kg_client = get_kg_client()
            
            report_content = final_task.result.replace("'", "\\'") # Simple escaping for Gremlin
            
            # Gremlin query to create the report and link it
            query = f"""
            def report = g.addV('Report')
                           .property('source', 'AIOpsWorkflow')
                           .property('content', '{report_content}')
                           .property('createdAt', '{datetime.utcnow().isoformat()}')
                           .next()
            
            def service = g.V().has('Service', 'name', '{service_name}').tryNext().orElse(null)
            if (service != null) {{
                g.V(report).addE('REPORT_FOR').to(service).iterate()
            }}
            
            def event = g.V().has('Event', 'eventId', '{workflow.event_id}').tryNext().orElse(null)
            if (event != null) {{
                g.V(report).addE('GENERATED_FROM').to(event).iterate()
            }}
            
            return report
            """
            
            # We need to run this async function in our sync thread
            asyncio.run(kg_client.execute_gremlin_query(query))
            logger.info("Successfully ingested AIOps report into Knowledge Graph.")
        
        except Exception as e:
            logger.error(f"Failed to ingest AIOps report into Knowledge Graph: {e}", exc_info=True)


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
        """Recursively processes a list of tasks, dispatching all that are ready."""
        all_blocks = workflow.get_all_tasks_recursive()
        completed_ids = {block.task_id for block in all_blocks if block.status == TaskStatus.COMPLETED}

        for block in blocks:
            if block.status == TaskStatus.PENDING and set(block.dependencies).issubset(completed_ids):
                if isinstance(block, WorkflowTask):
                    # NEW: Check for task-level condition before dispatching
                    if block.condition:
                        eval_context = self._get_evaluation_context(workflow)
                        try:
                            template = self._jinja_env.from_string(block.condition)
                            if template.render(eval_context):
                                self._dispatch_task(block, workflow)
                            else:
                                # If condition is not met, mark the task as cancelled (or a new 'SKIPPED' status)
                                logger.info(f"Skipping task '{block.task_id}' due to unmet condition.")
                                workflow_manager.update_task_status(workflow.workflow_id, block.task_id, TaskStatus.CANCELLED, result="Condition not met.")
                        except Exception as e:
                            logger.error(f"Failed to evaluate condition for task '{block.task_id}': {e}", exc_info=True)
                            workflow_manager.update_task_status(workflow.workflow_id, block.task_id, TaskStatus.FAILED, result=f"Condition evaluation failed: {e}")
                    else:
                        self._dispatch_task(block, workflow)
                elif isinstance(block, ConditionalBlock):
                    self._evaluate_conditional(block, workflow)
                elif isinstance(block, ApprovalBlock):
                    self._handle_approval_block(block, workflow)
            
            # This recursive call is problematic and can lead to re-processing.
            # A better approach would be a single pass. Refactoring this is out of scope for now.
            if hasattr(block, 'tasks') and block.tasks:
                self._process_blocks(block.tasks, workflow)


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
            
            properties = inject_trace_context({})
            self._task_producer.send(
                json.dumps(task_payload).encode('utf-8'),
                properties=properties
            )
            
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
        
        eval_context = self._get_evaluation_context(workflow)

        conditional_payload = {
            "block_id": block.task_id,
            "workflow_id": workflow.workflow_id,
            "evaluation_context": eval_context,
            "branches": [branch.dict() for branch in block.branches]
        }
        
        properties = inject_trace_context({})
        self._conditional_producer.send(
            json.dumps(conditional_payload).encode('utf-8'),
            properties=properties
        )
        
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