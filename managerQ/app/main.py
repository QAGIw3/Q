# managerQ/app/main.py
import os
import logging
import time
import yaml
import pulsar
from pyignite import Client as IgniteClient
import fastavro
import io
import signal
import sys
from collections import deque

# --- Configuration & Logging ---
logging.basicConfig(level="INFO")
logger = logging.getLogger("managerq")
running = True

# --- Schemas ---
# Must match H2M's outgoing schema
PROMPT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.h2m", "type": "record", "name": "PromptMessage",
    "fields": [
        {"name": "id", "type": "string"}, {"name": "prompt", "type": "string"},
        {"name": "model", "type": "string"}, {"name": "timestamp", "type": "long"}
    ]
})
# For agent registration
REGISTRATION_SCHEMA = fastavro.parse_schema({
    "namespace": "q.managerq", "type": "record", "name": "AgentRegistration",
    "fields": [
        {"name": "agent_id", "type": "string"},
        {"name": "task_topic", "type": "string"}
    ]
})

# --- Globals ---
# A deque for efficient round-robin
agent_topic_queue = deque()
pulsar_producers = {}

def shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received. Stopping manager...")
    running = False

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'manager.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_pulsar_producer(pulsar_client, topic):
    """Gets or creates a Pulsar producer for a given topic."""
    if topic not in pulsar_producers:
        logger.info(f"Creating producer for topic: {topic}")
        pulsar_producers[topic] = pulsar_client.create_producer(topic, schema=pulsar.schema.BytesSchema())
    return pulsar_producers[topic]

def handle_registration(msg, ignite_cache):
    """Processes an agent registration message."""
    bytes_reader = io.BytesIO(msg.data())
    record = next(fastavro.reader(bytes_reader, REGISTRATION_SCHEMA), None)
    if not record: return

    agent_id = record['agent_id']
    task_topic = record['task_topic']
    
    if not ignite_cache.get(agent_id):
        ignite_cache.put(agent_id, task_topic)
        agent_topic_queue.append(task_topic)
        logger.info(f"Registered new agent '{agent_id}' with topic '{task_topic}'. Queue size: {len(agent_topic_queue)}")

def handle_prompt(msg, pulsar_client):
    """Handles an incoming prompt and dispatches it to an agent."""
    if not agent_topic_queue:
        logger.warning("Received prompt but no agents are registered. Cannot dispatch.")
        # In a real system, you'd requeue this message.
        return

    # Round-robin: get the next agent topic and rotate the queue
    target_topic = agent_topic_queue[0]
    agent_topic_queue.rotate(-1)
    
    logger.info(f"Dispatching prompt to agent on topic: {target_topic}")
    producer = get_pulsar_producer(pulsar_client, target_topic)
    producer.send(msg.data())

def run_manager():
    config = load_config()
    pulsar_config = config['pulsar']
    ignite_config = config['ignite']

    pulsar_client = None
    ignite_client = None
    
    try:
        # Connect to Pulsar
        pulsar_client = pulsar.Client(pulsar_config['service_url'])
        
        # Connect to Ignite
        ignite_client = IgniteClient()
        ignite_client.connect(ignite_config['host'], ignite_config['port'])
        agent_registry_cache = ignite_client.get_or_create_cache(ignite_config['cache_name'])
        
        # Clear and populate agent queue from cache on startup
        agent_registry_cache.clear()
        logger.info("Cleared agent registry cache on startup.")
        
        # Create consumers
        prompt_consumer = pulsar_client.subscribe(pulsar_config['prompts_intake_topic'], pulsar_config['prompts_subscription'])
        registration_consumer = pulsar_client.subscribe(pulsar_config['agent_registration_topic'], pulsar_config['registration_subscription'])
        
        logger.info("managerQ is running. Waiting for agent registrations and prompts...")
        
        while running:
            try:
                # Prioritize checking for registrations
                reg_msg = registration_consumer.receive(timeout_millis=100)
                handle_registration(reg_msg, agent_registry_cache)
                registration_consumer.acknowledge(reg_msg)
            except pulsar.Timeout:
                pass # No registration, proceed to check for prompts

            try:
                prompt_msg = prompt_consumer.receive(timeout_millis=100)
                handle_prompt(prompt_msg, pulsar_client)
                prompt_consumer.acknowledge(prompt_msg)
            except pulsar.Timeout:
                continue # No prompt, continue loop

    except Exception as e:
        logger.error(f"A critical error occurred: {e}", exc_info=True)
    finally:
        if pulsar_client:
            for producer in pulsar_producers.values():
                producer.close()
            pulsar_client.close()
        if ignite_client:
            ignite_client.close()
        logger.info("ManagerQ has shut down.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    run_manager()
