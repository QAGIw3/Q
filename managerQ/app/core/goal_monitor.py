import logging
import time
import threading
import asyncio
from typing import Optional, Dict, Any
from pyignite import Client
from pyignite.exceptions import PyIgniteError

from managerQ.app.core.goal_manager import goal_manager
from managerQ.app.core.planner import planner, AmbiguousGoalError
from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.config import settings
from managerQ.app.models import Goal, Condition
from managerQ.app.models import Workflow, WorkflowStatus

logger = logging.getLogger(__name__)

class ProactiveGoalMonitor:
    """
    A background process that periodically evaluates platform goals against
    live and forecasted metrics from Ignite.
    """

    def __init__(self, poll_interval: int = 60):
        self.poll_interval = poll_interval
        self._client = Client()
        self._stats_cache = None
        self._forecast_cache = None
        self._goals = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def connect_to_ignite(self):
        """Connects to Ignite and gets the required caches."""
        try:
            self._client.connect(settings.ignite.addresses)
            self._stats_cache = self._client.get_or_create_cache("aiops_stats")
            self._forecast_cache = self._client.get_or_create_cache("aiops_forecasts")
            logger.info("GoalMonitor connected to Ignite and got caches.")
        except PyIgniteError as e:
            logger.error(f"Failed to connect GoalMonitor to Ignite: {e}", exc_info=True)
            raise

    def start(self):
        if self._running:
            logger.warning("ProactiveGoalMonitor is already running.")
            return
        
        try:
            self._client.connect(settings.ignite.addresses)
            self._stats_cache = self._client.get_or_create_cache("aiops_stats")
            self._forecast_cache = self._client.get_or_create_cache("aiops_forecasts")
            logger.info("ProactiveGoalMonitor connected to Ignite cache 'aiops_stats'.")
        except PyIgniteError as e:
            logger.error(f"Goal monitor failed to connect to Ignite: {e}", exc_info=True)
            # Do not start the loop if we can't connect to the stats cache.
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"ProactiveGoalMonitor started with a poll interval of {self.poll_interval}s.")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._client.is_connected():
            self._client.close()
        logger.info("ProactiveGoalMonitor stopped.")

    def _run_loop(self):
        while self._running:
            try:
                self.evaluate_goals()
            except Exception as e:
                logger.error(f"Error in ProactiveGoalMonitor loop: {e}", exc_info=True)
            time.sleep(self.poll_interval)

    def evaluate_goals(self):
        """Fetches latest metrics and forecasts, and evaluates all active goals."""
        active_goals = goal_manager.get_all_active_goals()
        if not active_goals:
            return

        logger.info(f"Evaluating {len(active_goals)} active goals...")
        for goal in active_goals:
            for condition in goal.conditions:
                # 1. Check current state
                current_value = self._get_current_metric(condition.service, condition.metric)
                if current_value is not None and self._is_breached(current_value, condition):
                    logger.warning(f"Goal '{goal.objective}' breached (Current)!", service=condition.service, metric=condition.metric, value=current_value)
                    self.trigger_remediation_workflow(goal, condition)
                    continue # Move to next goal if breached

                # 2. Check forecasted state
                forecasted_values = self._get_forecasted_metrics(condition.service, condition.metric)
                for ts, f_val in forecasted_values.items():
                    if self._is_breached(f_val, condition):
                        logger.warning(f"Goal '{goal.objective}' predicted to be breached at {ts}!", service=condition.service, metric=condition.metric, forecast_value=f_val)
                        # Modify the prompt for predicted breaches
                        self.trigger_remediation_workflow(goal, condition, is_predicted=True, prediction_time=ts)
                        break # Only trigger once per goal evaluation cycle

    def _get_current_metric(self, service: str, metric: str) -> Optional[float]:
        """Retrieves a metric value from the AIOps stats cache."""
        if not self._stats_cache:
            return None
        stats = self._stats_cache.get(service)
        if stats and metric in stats:
            return stats[metric]
        return None

    def _get_forecasted_metrics(self, service: str, metric: str) -> Dict[str, float]:
        """Retrieves forecasted metrics for a service from the forecast cache."""
        if not self._forecast_cache:
            return {}
        
        # The key is the service name, the value is a dict of {timestamp: forecast}
        forecasts = self._forecast_cache.get(service)
        return forecasts or {}

    def _is_breached(self, value: float, condition: Condition) -> bool:
        """Evaluates if a metric value breaches a condition."""
        op_map = {
            "<": lambda a, b: a < b,
            ">": lambda a, b: a > b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b,
        }
        return op_map[condition.operator](value, condition.value)

    def trigger_remediation_workflow(self, goal: Goal, failed_condition: Condition, is_predicted: bool = False, prediction_time: str = None):
        """
        Triggers a remediation workflow for a current or predicted breach.
        If the goal specifies a direct remediation workflow, it runs that.
        Otherwise, it asks the planner to create a new one.
        """
        logger.info(f"Triggering remediation for goal: {goal.objective}")

        # If a specific workflow is defined, use it directly.
        if goal.remediation_workflow_id:
            logger.info(f"Goal specifies direct remediation workflow: {goal.remediation_workflow_id}")
            workflow = workflow_manager.get_workflow(goal.remediation_workflow_id)
            if workflow:
                # We need to make sure the workflow is in a runnable state
                workflow.status = WorkflowStatus.RUNNING
                workflow_manager.update_workflow(workflow)
                logger.info(f"Triggered pre-defined workflow '{workflow.workflow_id}'.")
                return
            else:
                logger.error(f"Pre-defined workflow '{goal.remediation_workflow_id}' not found. Falling back to planner.")

        # Fallback to creating a new plan
        if is_predicted:
            prompt = (
                f"A future breach of the goal '{goal.objective}' is PREDICTED to occur around {prediction_time}. "
                f"The failing condition is: service '{failed_condition.service}' metric '{failed_condition.metric}' "
                f"is predicted to be {failed_condition.operator} {failed_condition.value}. "
                f"Create a workflow to proactively investigate and prevent this predicted failure."
            )
        else:
            prompt = (
                f"The platform goal '{goal.objective}' has been breached. "
                f"The failing condition is: service '{failed_condition.service}' metric '{failed_condition.metric}' "
                f"is {failed_condition.operator} {failed_condition.value}. "
                f"Create a workflow to diagnose the root cause and propose a remediation plan."
            )
        
        try:
            # Since this runs in a sync thread, we use asyncio.run()
            workflow = asyncio.run(planner.create_plan(prompt))
            workflow_manager.create_workflow(workflow)
            logger.info(f"Created and saved new remediation workflow '{workflow.workflow_id}'.")
        except AmbiguousGoalError as e:
            logger.critical(
                "The planner found an auto-generated remediation prompt to be ambiguous. This should not happen. "
                f"Prompt: '{prompt}'. Error: {e.clarifying_question}",
                exc_info=True
            )
        except Exception as e:
            logger.error(f"Failed to create remediation workflow: {e}", exc_info=True)

# Singleton instance
proactive_goal_monitor = ProactiveGoalMonitor() 