import logging
import json
import pulsar
import structlog
import asyncio
import yaml
from jinja2 import Template

from managerQ.app.core.task_dispatcher import task_dispatcher
from managerQ.app.core.agent_registry import agent_registry
from managerQ.app.api.dashboard_ws import manager as dashboard_manager
from managerQ.app.core.workflow_manager import workflow_manager
from managerQ.app.models import Workflow

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
        """Handles an error rate anomaly event by creating a new investigation workflow from a template."""
        payload = event_data.get("payload", {})
        service_name = payload.get("service_name")
        event_id = event_data.get("event_id")
        
        if not service_name or not event_id:
            logger.warning("Anomaly event received without a service_name or event_id", payload=payload)
            return

        logger.info(f"Anomaly detected in '{service_name}'. Creating investigation workflow from template.", event_id=event_id)
        
        # Broadcast the raw anomaly event to any connected dashboards
        asyncio.run(dashboard_manager.broadcast({
            "event_type": "anomaly_detected",
            "data": event_data
        }))

        try:
            with open("managerQ/app/workflow_templates/root_cause_analysis_workflow.yaml", 'r') as f:
                template_str = f.read()
            
            template = Template(template_str)
            rendered_yaml = template.render(
                service_name=service_name,
                original_event_payload=json.dumps(payload)
            )
            
            workflow_data = yaml.safe_load(rendered_yaml)
            
            # Create the workflow object
            workflow = Workflow(**workflow_data)
            workflow.event_id = event_id # Associate the event with the workflow
            
            workflow_manager.create_workflow(workflow)
            logger.info(f"Created and saved new investigation workflow '{workflow.workflow_id}' from template for event '{event_id}'.")

        except FileNotFoundError:
            logger.error("Could not find the root cause analysis workflow template.", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to create investigation workflow from template for event '{event_id}'", error=str(e), exc_info=True) 