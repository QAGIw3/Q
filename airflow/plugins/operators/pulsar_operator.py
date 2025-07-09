# airflow/plugins/operators/pulsar_operator.py
from airflow.models.baseoperator import BaseOperator
from airflow.utils.decorators import apply_defaults
import pulsar

class PulsarPublishOperator(BaseOperator):
    @apply_defaults
    def __init__(self, pulsar_conn_id: str, topic: str, message: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pulsar_conn_id = pulsar_conn_id
        self.topic = topic
        self.message = message

    def execute(self, context):
        # In a real system, the connection details would be fetched from Airflow's connection store.
        # For now, we'll hardcode the service URL.
        client = pulsar.Client('pulsar://pulsar:6650')
        producer = client.create_producer(self.topic)
        producer.send(self.message.encode('utf-8'))
        producer.close()
        client.close()
        self.log.info(f"Sent message to Pulsar topic: {self.topic}") 