import logging
import time
import threading
from typing import Optional, Dict

from kubernetes import client, config

from managerQ.app.core.task_dispatcher import task_dispatcher

logger = logging.getLogger(__name__)

# --- Kubernetes Client Setup ---
try:
    config.load_incluster_config()
    k8s_apps_v1 = client.AppsV1Api()
    logger.info("AutoScaler: Loaded in-cluster Kubernetes config.")
except config.ConfigException:
    try:
        config.load_kube_config()
        k8s_apps_v1 = client.AppsV1Api()
        logger.info("AutoScaler: Loaded local kubeconfig.")
    except config.ConfigException:
        logger.warning("Could not configure Kubernetes client for AutoScaler. Scaling will not work.")
        k8s_apps_v1 = None

# --- AutoScaler Logic ---

class AutoScaler:
    """
    Monitors agent task queues and scales Kubernetes deployments up or down.
    """
    def __init__(self, poll_interval: int = 30, scale_up_threshold: int = 10, scale_down_threshold: int = 1, max_replicas: int = 5, min_replicas: int = 1):
        self.poll_interval = poll_interval
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.max_replicas = max_replicas
        self.min_replicas = min_replicas
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the autoscaler loop in a background thread."""
        if not k8s_apps_v1:
            logger.error("Cannot start AutoScaler: Kubernetes client is not configured.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"AutoScaler started with a poll interval of {self.poll_interval}s.")

    def stop(self):
        """Stops the autoscaler loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        logger.info("AutoScaler stopped.")

    def _run_loop(self):
        """The main loop for checking queues and scaling deployments."""
        while self._running:
            try:
                self.check_and_scale_all()
            except Exception as e:
                logger.error(f"Error in AutoScaler loop: {e}", exc_info=True)
            time.sleep(self.poll_interval)

    def check_and_scale_all(self):
        """Checks all tracked agent personalities and scales them if needed."""
        if not task_dispatcher:
            return

        # We need to iterate over a copy of the items to avoid runtime errors
        # if the dictionary changes during iteration.
        pending_tasks_copy = dict(task_dispatcher.pending_tasks)

        for personality, count in pending_tasks_copy.items():
            deployment_name = f"agentq-{personality}"
            self.scale_deployment(deployment_name, count)

    def scale_deployment(self, deployment_name: str, queue_depth: int):
        """Applies scaling logic to a single deployment."""
        try:
            deployment = k8s_apps_v1.read_namespaced_deployment(name=deployment_name, namespace="default")
            current_replicas = deployment.spec.replicas
            
            new_replica_count = current_replicas

            # Scale up logic
            if queue_depth > self.scale_up_threshold and current_replicas < self.max_replicas:
                new_replica_count = current_replicas + 1
                logger.warning(f"High queue depth ({queue_depth}) for '{deployment_name}'. Scaling up to {new_replica_count} replicas.")
            
            # Scale down logic
            elif queue_depth <= self.scale_down_threshold and current_replicas > self.min_replicas:
                new_replica_count = current_replicas - 1
                logger.info(f"Low queue depth ({queue_depth}) for '{deployment_name}'. Scaling down to {new_replica_count} replicas.")

            if new_replica_count != current_replicas:
                patch_body = {"spec": {"replicas": new_replica_count}}
                k8s_apps_v1.patch_namespaced_deployment_scale(
                    name=deployment_name,
                    namespace="default",
                    body=patch_body
                )
        except client.ApiException as e:
            if e.status == 404:
                # This is not an error; it just means there's no specific deployment for this personality.
                pass
            else:
                logger.error(f"Kubernetes API error scaling '{deployment_name}': {e.body}")

# Singleton instance
autoscaler = AutoScaler() 