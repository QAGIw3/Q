import logging
import time
import threading
from typing import Optional, Dict, Any
from pyignite import Client
from pyignite.exceptions import PyIgniteError

from managerQ.app.core.goal_manager import goal_manager
from managerQ.app.core.planner import planner
from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.config import settings
from managerQ.app.models import Goal, Condition
from managerQ.app.models import WorkflowStatus

logger = logging.getLogger(__name__)

class ProactiveGoalMonitor:
    """
    A background process that monitors active goals and triggers workflows
    when goal conditions are breached.
    """

    def __init__(self, poll_interval: int = 60):
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._ignite_client = Client()
        self._stats_cache = None

    def start(self):
        if self._running:
            logger.warning("ProactiveGoalMonitor is already running.")
            return
        
        try:
            self._ignite_client.connect(settings.ignite.addresses)
            self._stats_cache = self._ignite_client.get_or_create_cache("aiops_stats")
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
        if self._ignite_client.is_connected():
            self._ignite_client.close()
        logger.info("ProactiveGoalMonitor stopped.")

    def _run_loop(self):
        while self._running:
            try:
                self.check_all_goals()
            except Exception as e:
                logger.error(f"Error in ProactiveGoalMonitor loop: {e}", exc_info=True)
            time.sleep(self.poll_interval)

    def check_all_goals(self):
        active_goals = goal_manager.get_all_active_goals()
        if not active_goals:
            return
            
        logger.info(f"Checking {len(active_goals)} active goals...")
        for goal in active_goals:
            self.check_single_goal(goal)

    def check_single_goal(self, goal: Goal):
        try:
            for condition in goal.conditions:
                metric_value = self.get_metric_value(condition.service, condition.metric)
                if metric_value is None:
                    continue

                if not self.evaluate_condition(metric_value, condition):
                    logger.warning(f"Goal '{goal.objective}' breached for service '{condition.service}'.")
                    self.trigger_remediation_workflow(goal, condition)
                    # Stop checking other conditions for this goal once one has failed
                    return
        except Exception as e:
            logger.error(f"Failed to check goal '{goal.goal_id}': {e}", exc_info=True)

    def get_metric_value(self, service: str, metric: str) -> Optional[float]:
        """Retrieves a metric value from the AIOps stats cache."""
        if not self._stats_cache:
            return None
        stats = self._stats_cache.get(service)
        if stats and metric in stats:
            return stats[metric]
        return None

    def evaluate_condition(self, value: float, condition: Condition) -> bool:
        """Evaluates a single condition against a metric value."""
        op_map = {
            "<": lambda a, b: a < b,
            ">": lambda a, b: a > b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b,
        }
        return op_map[condition.operator](value, condition.value)

    def trigger_remediation_workflow(self, goal: Goal, failed_condition: Condition):
        """
        Triggers a remediation workflow.
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

        # Fallback to creating a new plan if no specific workflow is defined.
        prompt = (
            f"The platform goal '{goal.objective}' has been breached. "
            f"The failing condition is: service '{failed_condition.service}' metric '{failed_condition.metric}' "
            f"is {failed_condition.operator} {failed_condition.value}. "
            f"Create a workflow to diagnose the root cause and propose a remediation plan."
        )
        
        try:
            workflow = planner.create_plan(prompt)
            workflow_manager.create_workflow(workflow)
            logger.info(f"Created and saved new remediation workflow '{workflow.workflow_id}'.")
        except Exception as e:
            logger.error(f"Failed to create remediation workflow: {e}", exc_info=True)

# Singleton instance
proactive_goal_monitor = ProactiveGoalMonitor() 