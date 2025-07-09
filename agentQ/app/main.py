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
import json
from opentelemetry import trace
import structlog

from shared.opentelemetry.tracing import setup_tracing
from shared.observability.logging_config import setup_logging
from shared.vault_client import VaultClient
from agentQ.app.core.context import ContextManager
from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.vectorstore_tool import vectorstore_tool
from agentQ.app.core.human_tool import human_tool
from agentQ.app.core.integrationhub_tool import integrationhub_tool
from agentQ.app.core.knowledgegraph_tool import knowledgegraph_tool
from agentQ.app.core.quantumpulse_tool import quantumpulse_tool

# Initialize tracing and logging
setup_tracing(app=None)
setup_logging()
logger = structlog.get_logger("agentq")

# --- Configuration & Logging ---
# logging.basicConfig(level=logging.INFO) # This line is removed as per the new_code
# logger = logging.getLogger("agentq") # This line is removed as per the new_code
running = True

# --- System Prompt ---
SYSTEM_PROMPT = """
You are an autonomous AI agent. Your goal is to answer the user's question or fulfill their request.

You operate in a ReAct (Reason, Act) loop. In each turn, you must use the following format:

Thought: [Your step-by-step reasoning about the current state, what you have learned, and what you need to do next. Be very detailed.]
Action: [A single JSON object describing the action to take. Must be one of `finish` or `call_tool`]

The `action` value MUST be a JSON object.

Example `Action` objects:
- To provide a final answer: `{"action": "finish", "answer": "The final answer to the user."}`
- To call a tool: `{"action": "call_tool", "tool_name": "name_of_tool", "parameters": {"arg1": "value1", "arg2": "value2"}}`

You can call tools sequentially to gather information. After each tool call, you will receive an "Observation" with the result. Use these observations to inform your next thought and action. Continue until you have enough information to provide a final answer.

Here are the tools you have available:
{tools}

Begin!
"""

# --- Schemas & Config ---
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
    logger.info("Registering agent", agent_id=agent_id, topic=task_topic)
    message = {"agent_id": agent_id, "task_topic": task_topic}
    buf = io.BytesIO()
    fastavro.writer(buf, REGISTRATION_SCHEMA, [message])
    producer.send(buf.getvalue())
    logger.info("Registration message sent.")

# --- ReAct Loop ---
@tracer.start_as_current_span("react_loop")
def react_loop(prompt_data, context_manager, toolbox, client, llm_config):
    """The main ReAct loop for processing a user request."""
    user_prompt = prompt_data.get("prompt")
    conversation_id = prompt_data.get("id") # Assuming prompt_id is the conversation_id

    history = context_manager.get_history(conversation_id)
    history.append({"role": "user", "content": user_prompt})

    max_turns = 5
    for turn in range(max_turns):
        current_span = trace.get_current_span()
        current_span.set_attribute("react.turn", turn)

        # 1. Build the prompt
        full_prompt = history + [{"role": "system", "content": SYSTEM_PROMPT.format(tools=toolbox.get_tool_descriptions())}]
        
        # 2. Call the LLM
        completion = client.chat.completions.create(
            model=llm_config['model'],
            messages=full_prompt
        )
        response_text = completion.choices[0].message.content
        history.append({"role": "assistant", "content": response_text})

        # 3. Parse the response
        try:
            thought = response_text.split("Action:")[0].replace("Thought:", "").strip()
            action_str = response_text.split("Action:")[1].strip()
            action_json = json.loads(action_str)
            current_span.add_event("LLM Response Parsed", {"thought": thought, "action": json.dumps(action_json)})
        except (IndexError, json.JSONDecodeError) as e:
            logger.error("Could not parse LLM response", response=response_text, error=str(e))
            return "Error: Could not parse my own action. I will try again."

        # 4. Execute the action
        if action_json.get("action") == "finish":
            final_answer = action_json.get("answer", "No answer provided.")
            context_manager.append_to_history(conversation_id, history)
            return final_answer
        elif action_json.get("action") == "call_tool":
            tool_name = action_json.get("tool_name")
            parameters = action_json.get("parameters", {})
            logger.info("Executing tool", tool_name=tool_name, parameters=parameters)
            observation = toolbox.execute_tool(tool_name, **parameters)
            history.append({"role": "system", "content": f"Tool Observation: {observation}"})
        else:
            history.append({"role": "system", "content": "Error: Invalid action specified."})

    context_manager.append_to_history(conversation_id, history)
    return "Error: Reached maximum turns without a final answer."

def run_agent():
    config = load_config()
    pulsar_config = config['pulsar']
    llm_config = config['llm']
    
    agent_id = f"agentq-{uuid.uuid4()}"
    task_topic = f"persistent://public/default/q.agentq.tasks.{agent_id}"
    subscription_name = f"agentq-sub-{agent_id}"

    # Initialize components
    context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=agent_id)
    toolbox = Toolbox()
    toolbox.register_tool(vectorstore_tool)
    toolbox.register_tool(human_tool)
    toolbox.register_tool(integrationhub_tool)
    toolbox.register_tool(knowledgegraph_tool)
    toolbox.register_tool(quantumpulse_tool)
    
    pulsar_client = None
    try:
        # Fetch secrets from Vault instead of environment variables
        vault_client = VaultClient()
        openai_api_key = vault_client.read_secret("secret/data/openai", "api_key")

        pulsar_client = pulsar.Client(pulsar_config['service_url'])
        openai_client = OpenAI(api_key=openai_api_key)
        context_manager.connect()

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
            logger.info("Agent running", agent_id=agent_id, topic=task_topic)

            while running:
                try:
                    msg = consumer.receive(timeout_millis=1000)
                    bytes_reader = io.BytesIO(msg.data())
                    prompt_data = next(fastavro.reader(bytes_reader, PROMPT_SCHEMA), None)
                    if not prompt_data:
                        consumer.acknowledge(msg)
                        continue

                    logger.info("Received task", task_id=prompt_data.get("id"))
                    final_result = react_loop(prompt_data, context_manager, toolbox, openai_client, llm_config)
                    
                    # Publish the final result
                    result_message = {
                        "id": prompt_data.get("id"), "result": final_result, 
                        "llm_model": llm_config['model'], "prompt": prompt_data.get("prompt"),
                        "timestamp": int(time.time() * 1000)
                    }
                    buf = io.BytesIO()
                    fastavro.writer(buf, RESULT_SCHEMA, [result_message])
                    result_producer.send(buf.getvalue())
                    logger.info("Published result", task_id=prompt_data.get("id"))

                    consumer.acknowledge(msg)
                except pulsar.Timeout:
                    continue
                except Exception as e:
                    logger.error("An error occurred in the main loop", error=str(e), exc_info=True)
                    if 'msg' in locals():
                        consumer.negative_acknowledge(msg)
                    time.sleep(5)

    except Exception as e:
        logger.critical("A critical error occurred, agent shutting down", error=str(e), exc_info=True)
    finally:
        if pulsar_client:
            pulsar_client.close()
        context_manager.close()
        logger.info("Agent has shut down", agent_id=agent_id)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    run_agent()
