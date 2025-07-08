# agentQ/app/main.py
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import logging
import time
import yaml
import pulsar
from openai import OpenAI
import fastavro
import io
import signal
import uuid
from opentelemetry import trace

from shared.opentelemetry.tracing import setup_tracing

# Initialize tracing
SERVICE_NAME = "agentq-service"
setup_tracing(SERVICE_NAME)
tracer = trace.get_tracer(__name__)

# --- Configuration & Logging ---
logging.basicConfig(level="INFO")
logger = logging.getLogger("agentq")
running = True

# --- Signal Handler & Schemas ---
def shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received. Stopping agent...")
    running = False

PROMPT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.h2m", "type": "record", "name": "PromptMessage",
    "fields": [
        {"name": "id", "type": "string"}, {"name": "prompt", "type": "string"},
        {"name": "model", "type": "string"}, {"name": "timestamp", "type": "long"}
    ]
})
RESULT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ResultMessage",
    "fields": [
        {"name": "id", "type": "string"}, {"name": "result", "type": "string"},
        {"name": "llm_model", "type": "string"}, {"name": "prompt", "type": "string"},
        {"name": "timestamp", "type": "long"}
    ]
})
REGISTRATION_SCHEMA = fastavro.parse_schema({
    "namespace": "q.managerq", "type": "record", "name": "AgentRegistration",
    "fields": [{"name": "agent_id", "type": "string"}, {"name": "task_topic", "type": "string"}]
})

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'agent.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def register_with_manager(producer, agent_id, task_topic):
    """Sends a registration message to the manager."""
    logger.info(f"Registering agent '{agent_id}' with topic '{task_topic}'")
    message = {"agent_id": agent_id, "task_topic": task_topic}
    buf = io.BytesIO()
    fastavro.writer(buf, REGISTRATION_SCHEMA, [message])
    producer.send(buf.getvalue())
    logger.info("Registration message sent.")

@tracer.start_as_current_span("process_agent_message")
def process_message(msg, producer, client, llm_config):
    """Processes a single message from the dedicated task topic."""
    current_span = trace.get_current_span()
    try:
        bytes_reader = io.BytesIO(msg.data())
        prompt_data = next(fastavro.reader(bytes_reader, PROMPT_SCHEMA), None)
        if not prompt_data: return

        prompt_id = prompt_data.get("id")
        prompt_text = prompt_data.get("prompt")
        logger.info(f"Received prompt [{prompt_id}]")
        current_span.set_attribute("message.id", prompt_id)

        # The OpenAI call is automatically traced by the RequestsInstrumentor
        logger.info("Sending prompt to OpenAI...")
        completion = client.chat.completions.create(
            model=llm_config['model'],
            messages=[{"role": "user", "content": prompt_text}]
        )
        result_text = completion.choices[0].message.content
        logger.info(f"Received result from OpenAI for prompt [{prompt_id}]")

        with tracer.start_as_current_span("publish_result_to_pulsar") as span:
            result_message = {
                "id": prompt_id, "result": result_text, "llm_model": llm_config['model'],
                "prompt": prompt_text, "timestamp": int(time.time() * 1000)
            }
            span.set_attribute("pulsar.topic", producer.topic())
            span.set_attribute("message.id", prompt_id)
            
            buf = io.BytesIO()
            fastavro.writer(buf, RESULT_SCHEMA, [result_message])
            producer.send(buf.getvalue())
            logger.info(f"Published result for prompt [{prompt_id}]")

    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)
        current_span.record_exception(e)
        current_span.set_status(trace.Status(trace.StatusCode.ERROR, "Agent message processing failed"))

def run_agent():
    config = load_config()
    pulsar_config = config['pulsar']
    llm_config = config['llm']
    
    agent_id = f"agentq-{uuid.uuid4()}"
    task_topic = f"persistent://public/default/q.agentq.tasks.{agent_id}"
    subscription_name = f"agentq-sub-{agent_id}"

    pulsar_client = None
    try:
        pulsar_client = pulsar.Client(pulsar_config['service_url'])
        openai_client = OpenAI()

        # Producer for registration
        reg_producer = pulsar_client.create_producer(pulsar_config['registration_topic'], schema=pulsar.schema.BytesSchema())
        register_with_manager(reg_producer, agent_id, task_topic)
        reg_producer.close()
        
        # Consumer for dedicated tasks
        consumer = pulsar_client.subscribe(task_topic, subscription_name)
        
        # Producer for results
        result_producer = pulsar_client.create_producer(pulsar_config['results_topic'], schema=pulsar.schema.BytesSchema())
        
        # This span will be the parent for all processing spans inside the loop
        with tracer.start_as_current_span("agent_main_loop") as parent_span:
            parent_span.set_attribute("agent.id", agent_id)
            parent_span.set_attribute("agent.task_topic", task_topic)
            logger.info(f"Agent '{agent_id}' is running. Listening on '{task_topic}'.")

            while running:
                try:
                    msg = consumer.receive(timeout_millis=1000)
                    process_message(msg, result_producer, openai_client, llm_config)
                    consumer.acknowledge(msg)
                except pulsar.Timeout:
                    continue
                except Exception as e:
                    logger.error(f"An error occurred in the main loop: {e}")
                    if 'msg' in locals():
                        consumer.negative_acknowledge(msg)
                    time.sleep(5)

    except Exception as e:
        logger.error(f"A critical error occurred: {e}", exc_info=True)
    finally:
        if pulsar_client:
            pulsar_client.close()
        logger.info(f"Agent '{agent_id}' has shut down.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    run_agent()
