import pulsar
import json
import time

from app.core.engine import run_flow
from app.models.flow import Flow

PULSAR_URL = 'pulsar://localhost:6650'
TRIGGER_TOPIC = 'persistent://public/default/integration-hub-triggers'
SUBSCRIPTION_NAME = 'integration-hub-worker-subscription'

def main():
    print("--- Starting Integration Hub Worker ---")
    client = pulsar.Client(PULSAR_URL)
    consumer = client.subscribe(
        TRIGGER_TOPIC,
        subscription_name=SUBSCRIPTION_NAME,
        consumer_type=pulsar.ConsumerType.Shared
    )

    print(f"Subscribed to {TRIGGER_TOPIC}. Waiting for messages...")

    while True:
        try:
            msg = consumer.receive()
            try:
                payload = json.loads(msg.data().decode('utf-8'))
                print(f"Received trigger for flow: {payload['flow_definition']['name']}")
                
                # Re-create the Flow object from the definition
                flow_definition = payload['flow_definition']
                flow = Flow(**flow_definition)

                # Pass trigger_data to run_flow
                trigger_data = payload.get('trigger_data', {})
                run_flow(flow, data_context=trigger_data)

                consumer.acknowledge(msg)
            except Exception as e:
                # Message failed to be processed
                print(f"ERROR: Failed to process message {msg.message_id()}: {e}")
                consumer.negative_acknowledge(msg)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(5) # Avoid rapid-fire errors

    client.close()
    print("--- Integration Hub Worker Shutting Down ---")

if __name__ == '__main__':
    main() 