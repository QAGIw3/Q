import logging
import json
import pulsar
import structlog

from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.core.agent_registry import agent_registry
from managerQ.app.api.dashboard_ws import manager as dashboard_manager

logger = structlog.get_logger(__name__)

class EventListener:
    """
    Listens for platform events and triggers agent tasks accordingly.
    """

    def __init__(self, service_url: str, event_topic: str):
        self.service_url = service_url
        self.event_topic = event_topic
        self.client = None
        self.consumer = None
        self._running = False

    def start(self):
        """Starts the Pulsar consumer in a separate thread."""
        logger.info("Starting EventListener...", topic=self.event_topic)
        self.client = pulsar.Client(self.service_url)
        self.consumer = self.client.subscribe(
            self.event_topic,
            subscription_name="managerq-event-listener-sub",
            consumer_type=pulsar.ConsumerType.Shared
        )
        self._running = True
        
        # In a real application, you'd run this in a background thread.
        # For simplicity, we'll assume the main event loop allows this.
        # This is a blocking call, so this approach needs to be refined in a real system.
        logger.info("EventListener started and waiting for messages.")
        while self._running:
            try:
                msg = self.consumer.receive(timeout_millis=1000)
                self.handle_message(msg)
                self.consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error("Error in EventListener loop", error=str(e), exc_info=True)
                if 'msg' in locals():
                    self.consumer.negative_acknowledge(msg)
    
    def stop(self):
        self._running = False
        if self.consumer:
            self.consumer.close()
        if self.client:
            self.client.close()
        logger.info("EventListener stopped.")

    def handle_message(self, msg):
        """Processes a single message from the event topic."""
        try:
            event_data = json.loads(msg.data().decode('utf-8'))
            event_type = event_data.get("event_type")
            logger.info("Received platform event", event_type=event_type)

            if event_type == "anomaly.detected.error_rate":
                self.handle_anomaly_event(event_data)
        
        except json.JSONDecodeError:
            logger.warning("Could not decode event message", raw_data=msg.data())
        except Exception as e:
            logger.error("Failed to handle event message", error=str(e), exc_info=True)

    def handle_anomaly_event(self, event_data: dict):
        """Handles an error rate anomaly event by dispatching a task and broadcasting to dashboards."""
        payload = event_data.get("payload", {})
        service_name = payload.get("service_name")
        
        if not service_name:
            logger.warning("Anomaly event received without a service_name", payload=payload)
            return

        logger.info(f"Anomaly detected in '{service_name}'. Finding a DevOps agent to investigate.")
        
        # Broadcast the raw anomaly event to any connected dashboards
        dashboard_manager.broadcast({
            "event_type": "anomaly_detected",
            "data": event_data
        })
        
        # Find a registered DevOps agent
        devops_agent = agent_registry.find_agent_by_prefix("devops-agent")
        
        if not devops_agent:
            logger.error("No DevOps agent is currently registered. Cannot dispatch anomaly task.")
            return

        prompt = (
            f"An alert has been triggered for the service '{service_name}'. "
            f"The service is experiencing an anomalous error rate. "
            f"Payload: {json.dumps(payload)}. "
            "Please investigate the root cause and propose a solution."
        )
        
        task_dispatcher.dispatch_task(
            agent_id=devops_agent['agent_id'],
            prompt=prompt,
            model="default" # The agent will use its configured model
        )
        logger.info(f"Dispatched anomaly investigation task to agent '{devops_agent['agent_id']}'.") 