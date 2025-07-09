import logging
import json
import pulsar
from shared.pulsar_client import shared_pulsar_client

AUDIT_TOPIC = "persistent://public/default/q-platform-audit"

def get_audit_logger():
    """
    Configures and returns a logger for audit events that publishes to Pulsar.
    """
    producer = shared_pulsar_client.create_producer(AUDIT_TOPIC)
    
    class PulsarAuditHandler(logging.Handler):
        def emit(self, record):
            log_entry = self.format(record)
            producer.send(log_entry.encode('utf-8'))

    handler = PulsarAuditHandler()
    logger = logging.getLogger('audit')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger

def audit_log(action: str, user: str, details: dict):
    """
    Logs an audit event.
    
    Args:
        action (str): The action that was performed (e.g., 'approve_task').
        user (str): The user who performed the action.
        details (dict): A dictionary of relevant details.
    """
    logger = get_audit_logger()
    log_entry = {
        "action": action,
        "user": user,
        "details": details
    }
    logger.info(json.dumps(log_entry)) 