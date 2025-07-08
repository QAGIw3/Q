import pulsar
import json
from ..models.flow import Flow

# For now, we'll hardcode the Pulsar service URL and topic.
# In a real application, this would come from configuration.
PULSAR_URL = 'pulsar://localhost:6650'
TRIGGER_TOPIC = 'persistent://public/default/integration-hub-triggers'

_client = None
_producer = None

def get_pulsar_producer():
    """
    Initializes and returns a singleton Pulsar producer.
    """
    global _client, _producer
    if _producer is None:
        if _client is None:
            _client = pulsar.Client(PULSAR_URL)
        _producer = _client.create_producer(TRIGGER_TOPIC)
    return _producer

def publish_flow_trigger(flow: Flow, trigger_data: dict = None):
    """
    Serializes a flow and publishes it to the trigger topic.
    """
    producer = get_pulsar_producer()
    payload = {
        "flow_definition": flow.dict(),
        "trigger_data": trigger_data or {}
    }
    producer.send(json.dumps(payload).encode('utf-8'))

def close_pulsar_producer():
    """
    Closes the producer and client. Should be called on application shutdown.
    """
    global _client, _producer
    if _producer:
        _producer.close()
    if _client:
        _client.close()
    _producer = None
    _client = None 