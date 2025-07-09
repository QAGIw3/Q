# agentQ/planner_agent.py
import logging
import threading
import pulsar
import io
import time
import json
import fastavro

from agentQ.app.core.prompts import PLANNER_PROMPT_TEMPLATE
from shared.q_messaging_schemas.schemas import PROMPT_SCHEMA, RESULT_SCHEMA
from agentQ.app.main import register_with_manager
from shared.q_pulse_client.models import QPChatRequest, QPChatMessage

logger = logging.getLogger(__name__)

AGENT_ID = "planner_agent"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"
REGISTRATION_TOPIC = "persistent://public/default/q.managerq.agent.registrations"

def run_planner_agent(pulsar_client, qpulse_client, llm_config):
    """
    The main function for the Planner agent.
    """
    logger.info("Starting Planner Agent...")
    
    registration_producer = pulsar_client.create_producer(REGISTRATION_TOPIC)
    result_producer = pulsar_client.create_producer(llm_config['result_topic'])
    
    register_with_manager(registration_producer, AGENT_ID, TASK_TOPIC)
    
    consumer = pulsar_client.subscribe(TASK_TOPIC, f"agentq-sub-{AGENT_ID}")

    def consumer_loop():
        while True:
            try:
                msg = consumer.receive(timeout_millis=1000)
                prompt_data = next(fastavro.reader(io.BytesIO(msg.data()), PROMPT_SCHEMA))
                
                logger.info(f"Planner agent received goal: {prompt_data['prompt']}")

                # Format the prompt and call the LLM
                planner_prompt = PLANNER_PROMPT_TEMPLATE.format(user_prompt=prompt_data['prompt'])
                messages = [QPChatMessage(role="user", content=planner_prompt)]
                request = QPChatRequest(model=llm_config['model'], messages=messages, temperature=0.0)
                
                response = qpulse_client.get_chat_completion(request)
                plan_json_str = response.choices[0].message.content

                # The result is the raw JSON string of the plan
                result_message = {
                    "id": prompt_data["id"],
                    "result": plan_json_str,
                    "llm_model": response.model,
                    "prompt": prompt_data["prompt"],
                    "timestamp": int(time.time() * 1000),
                    "workflow_id": prompt_data["workflow_id"],
                    "task_id": prompt_data["task_id"],
                    "agent_personality": AGENT_ID
                }
                buf = io.BytesIO()
                fastavro.writer(buf, RESULT_SCHEMA, [result_message])
                result_producer.send(buf.getvalue())
                
                consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in Planner agent loop: {e}", exc_info=True)

    threading.Thread(target=consumer_loop, daemon=True).start()
    logger.info("Planner Agent consumer thread started.") 