# ResultListener/app/main.py
import pulsar
import logging
import signal
import sys
import io
import fastavro

# --- Configuration ---
LOG_LEVEL = "INFO"
PULSAR_SERVICE_URL = "pulsar://localhost:6650"
RESULTS_TOPIC = "q.agentq.results"
SUBSCRIPTION_NAME = "result-listener-subscription"

# --- Logging ---
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("result-listener")

# --- Globals ---
running = True

# --- Signal Handler ---
def shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received. Stopping listener...")
    running = False

# --- Avro Schema ---
# Must match the schema used by agentQ to produce results
RESULT_SCHEMA = {
    "namespace": "q.agentq", "type": "record", "name": "ResultMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "result", "type": "string"},
        {"name": "llm_model", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "timestamp", "type": "long"}
    ]
}
PARSED_RESULT_SCHEMA = fastavro.parse_schema(RESULT_SCHEMA)

def listen_for_results():
    """Connects to Pulsar and prints results from the results topic."""
    pulsar_client = None
    try:
        pulsar_client = pulsar.Client(PULSAR_SERVICE_URL)
        consumer = pulsar_client.subscribe(RESULTS_TOPIC, SUBSCRIPTION_NAME)
        
        logger.info(f"ResultListener is running. Subscribed to '{RESULTS_TOPIC}'.")
        
        while running:
            try:
                msg = consumer.receive(timeout_millis=1000)
                
                # Decode Avro message
                bytes_reader = io.BytesIO(msg.data())
                records = list(fastavro.reader(bytes_reader, PARSED_RESULT_SCHEMA))
                if records:
                    result_data = records[0]
                    
                    # Print formatted output
                    print("\n" + "="*80)
                    print(f"✅ New Result Received [ID: {result_data.get('id')}]")
                    print("-"*80)
                    print(f"💬 Prompt:\n{result_data.get('prompt')}")
                    print("-"*80)
                    print(f"🤖 LLM ({result_data.get('llm_model')}):\n{result_data.get('result')}")
                    print("="*80 + "\n")

                consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue # No message, just loop again
            except Exception as e:
                logger.error(f"Failed to process message: {e}", exc_info=True)
                if 'msg' in locals():
                    consumer.negative_acknowledge(msg)

    except Exception as e:
        logger.error(f"A critical error occurred: {e}", exc_info=True)
    finally:
        if pulsar_client:
            pulsar_client.close()
            logger.info("Pulsar client closed.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    listen_for_results()
