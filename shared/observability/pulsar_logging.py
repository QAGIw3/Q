import logging
import json
from shared.pulsar_client import shared_pulsar_client

class PulsarLogHandler(logging.Handler):
    """
    A logging handler that sends log records to a Pulsar topic.
    """
    def __init__(self, topic: str, service_name: str):
        super().__init__()
        self.topic = topic
        self.service_name = service_name

    def emit(self, record: logging.LogRecord):
        """
        Formats the log record and sends it to Pulsar.
        """
        try:
            # The record.msg is already a JSON string from the structlog processor
            log_data = json.loads(record.getMessage())
            
            # Add service name for routing and filtering
            log_data['service_name'] = self.service_name
            
            shared_pulsar_client.publish_message(self.topic, log_data)
        except Exception:
            # If logging to Pulsar fails, fall back to stderr
            self.handleError(record) 