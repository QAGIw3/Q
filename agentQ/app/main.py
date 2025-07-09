# agentQ/app/main.py
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import logging
import time
import yaml
import pulsar
import asyncio
import fastavro
import io
import signal
import uuid
import json
from opentelemetry import trace
import structlog
import httpx

from shared.opentelemetry.tracing import setup_tracing
from shared.observability.logging_config import setup_logging
from shared.vault_client import VaultClient
from shared.pulsar_client import shared_pulsar_client
from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import QPChatRequest, QPChatMessage
from agentQ.app.core.context import ContextManager
from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.vectorstore_tool import vectorstore_tool
from agentQ.app.core.human_tool import human_tool
from agentQ.app.core.integrationhub_tool import integrationhub_tool
from agentQ.app.core.knowledgegraph_tool import knowledgegraph_tool, summarize_activity_tool, find_experts_tool
from agentQ.app.core.quantumpulse_tool import quantumpulse_tool
from agentQ.app.core.memory_tool import save_memory_tool, search_memory_tool
from agentQ.app.core.github_tool import github_tool
from agentQ.app.core.ui_generation_tool import generate_table_tool
from agentQ.app.core.meta_tools import list_tools_tool
from agentQ.app.core.airflow_tool import trigger_dag_tool, get_dag_status_tool
from agentQ.app.core.delegation_tool import delegation_tool
from agentQ.app.core.code_search_tool import code_search_tool
from agentQ.app.core.prompts import REFLEXION_PROMPT_TEMPLATE
from agentQ.devops_agent import setup_devops_agent, DEVOPS_SYSTEM_PROMPT, AGENT_ID as DEVOPS_AGENT_ID, TASK_TOPIC as DEVOPS_TASK_TOPIC
from agentQ.data_analyst_agent import setup_data_analyst_agent, DATA_ANALYST_SYSTEM_PROMPT, AGENT_ID as DA_AGENT_ID, TASK_TOPIC as DA_TASK_TOPIC
from agentQ.knowledge_engineer_agent import setup_knowledge_engineer_agent, KNOWLEDGE_ENGINEER_SYSTEM_PROMPT, AGENT_ID as KE_AGENT_ID, TASK_TOPIC as KE_TASK_TOPIC
from agentQ.predictive_analyst_agent import setup_predictive_analyst_agent, PREDICTIVE_ANALYST_SYSTEM_PROMPT, AGENT_ID as PA_AGENT_ID, TASK_TOPIC as PA_TASK_TOPIC
from agentQ.docs_agent import setup_docs_agent, DOCS_AGENT_SYSTEM_PROMPT, AGENT_ID as DOCS_AGENT_ID, TASK_TOPIC as DOCS_TASK_TOPIC

# Initialize tracing and logging
setup_tracing(app=None)
setup_logging(service_name="agentQ")
logger = structlog.get_logger("agentq")

# --- Configuration & Logging ---
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

**IMPORTANT STRATEGIES:**
1.  **Delegate When Necessary:** If the user's request requires specialized knowledge (e.g., analyzing system logs, running a complex data query), you **MUST** delegate it to the appropriate specialist agent using the `delegate_task` tool.
2.  **Collaborate via Shared Context:** When working on a multi-agent workflow, use `read_shared_context` at the beginning of your task to see findings from other agents. Use `update_shared_context` to post your own findings for others to see. The `workflow_id` required for these tools will be provided in the prompt.
3.  **Memory First:** Before starting a complex task, especially one that feels familiar, use the `search_memory` tool to see if you've already solved a similar problem.
4.  **Learn from Mistakes:** If a task seems complex or might fail, use the `retrieve_reflexion` tool with the user's prompt as the parameter.
5.  **Visualize Data:** If the user asks for data that would be best viewed in a table, use the `generate_table` tool.
6.  **Summarize Your Work:** At the end of a successful conversation, you will be asked to generate a structured JSON object representing your memory of the task. This memory object should include a `summary`, the `entities` involved, `key_relationships` you discovered, the final `outcome`, the original `full_prompt`, and your `final_answer`. This is your absolute final action before finishing the task.

Here are the tools you have available:
{tools}

Begin!
"""

# --- Schemas & Config ---
PROMPT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.managerq", "type": "record", "name": "PromptMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "model", "type": "string"},
        {"name": "timestamp", "type": "long"},
        {"name": "workflow_id", "type": ["null", "string"], "default": None},
        {"name": "task_id", "type": ["null", "string"], "default": None},
    ]
})
RESULT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ResultMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "result", "type": "string"},
        {"name": "llm_model", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "timestamp", "type": "long"},
        {"name": "workflow_id", "type": ["null", "string"], "default": None},
        {"name": "task_id", "type": ["null", "string"], "default": None},
        {"name": "agent_personality", "type": ["null", "string"], "default": None},
    ]
})
REGISTRATION_SCHEMA = fastavro.parse_schema({
    "namespace": "q.managerq", "type": "record", "name": "AgentRegistration",
    "fields": [{"name": "agent_id", "type": "string"}, {"name": "task_topic", "type": "string"}]
})
THOUGHT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ThoughtMessage",
    "fields": [
        {"name": "conversation_id", "type": "string"},
        {"name": "thought", "type": "string"},
        {"name": "timestamp", "type": "long"},
    ]
})

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'agent.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_agent_memory():
    """
    Ensures the 'agent_memory' collection exists in VectorStoreQ on startup.
    """
    logger.info("Setting up agent memory collection in VectorStoreQ...")
    try:
        # This requires the service to have a valid token with an 'admin' or 'service-account' role.
        # This part of the code is simplified and assumes such a token is available.
        # In a real production system, this agent would use a service account token.
        # For now, we will need to manually create this collection if auth fails.
        # A better approach would be to have a proper service account mechanism.
        
        # TODO: Use a real service account token.
        # This is a placeholder and will not work without a valid JWT.
        headers = {"Authorization": "Bearer YOUR_SERVICE_ACCOUNT_TOKEN"}
        
        url = "http://localhost:8001/api/v1/management/create-collection"
        
        payload = {
            "schema": {
                "collection_name": "agent_memory",
                "description": "Long-term memory for autonomous agents.",
                "fields": [
                    {"name": "memory_id", "dtype": "VarChar", "is_primary": True, "max_length": 36},
                    {"name": "summary_text", "dtype": "VarChar", "max_length": 1000},
                    {"name": "vector", "dtype": "FloatVector", "dim": 768}
                ],
                "enable_dynamic_field": False
            },
            "index": {
                "field_name": "vector",
                "index_type": "HNSW",
                "metric_type": "COSINE"
            }
        }
        
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code == 401 or response.status_code == 403:
                logger.warning("Could not create 'agent_memory' collection due to auth error. This may need to be created manually.", status=response.status_code, response=response.text)
            elif response.status_code not in [200, 201, 409]: # 409 Conflict is OK (already exists)
                 response.raise_for_status()
            logger.info("Agent memory setup check completed.", response=response.json())

    except Exception as e:
        logger.error("Failed to set up agent memory collection. The agent may not be able to remember past conversations.", error=str(e), exc_info=True)


def register_with_manager(producer, agent_id, task_topic):
    """Sends a registration message to the manager."""
    logger.info("Registering agent", agent_id=agent_id, topic=task_topic)
    message = {"agent_id": agent_id, "task_topic": task_topic}
    buf = io.BytesIO()
    fastavro.writer(buf, REGISTRATION_SCHEMA, [message])
    producer.send(buf.getvalue())
    logger.info("Registration message sent.")

def generate_and_save_reflexion(user_prompt: str, scratchpad: list, context_manager: ContextManager, qpulse_client: QuantumPulseClient, llm_config: dict):
    """Generates a reflexion and saves it to the memory cache."""
    logger.info("Generating reflexion for failed task...")
    
    # Format the scratchpad for inclusion in the prompt
    scratchpad_str = "\n".join([f"[{item['type']}] {item['content']}" for item in scratchpad])
    
    reflexion_prompt = REFLEXION_PROMPT_TEMPLATE.format(
        user_prompt=user_prompt,
        scratchpad=scratchpad_str
    )
    
    try:
        messages = [QPChatMessage(role="user", content=reflexion_prompt)]
        request = QPChatRequest(model=llm_config['model'], messages=messages)
        
        response = asyncio.run(qpulse_client.get_chat_completion(request))
        reflexion_text = response.choices[0].message.content
        logger.info("Generated reflexion", reflexion=reflexion_text)
        
        # Save the reflexion to a dedicated cache for future use
        context_manager.save_reflexion(user_prompt, reflexion_text)
        
    except Exception as e:
        logger.error("Failed to generate or save reflexion.", error=str(e), exc_info=True)


@tracer.start_as_current_span("react_loop")
def react_loop(prompt_data, context_manager, toolbox, qpulse_client, llm_config, thoughts_producer):
    """The main ReAct loop for processing a user request."""
    user_prompt = prompt_data.get("prompt")
    conversation_id = prompt_data.get("id") # Assuming prompt_id is the conversation_id

    # Initialize the scratchpad for this loop
    scratchpad = []
    
    history = context_manager.get_history(conversation_id)
    
    if not history: # Only perform these checks for the very first turn
        # --- Automatic Reflexion Retrieval Step ---
        logger.info("New conversation, checking for past reflexions...")
        past_reflexion = context_manager.get_reflexion(user_prompt)
        if past_reflexion:
            reflexion_observation = f"System Directive: A previous attempt at a similar task failed. Heed this advice: {past_reflexion}"
            history.append({"role": "system", "content": reflexion_observation})
            scratchpad.append({"type": "reflexion", "content": reflexion_observation, "timestamp": time.time()})

        # --- Memory Retrieval Step ---
        logger.info("Searching long-term memory...")
        initial_memories = toolbox.execute_tool("search_memory", query=user_prompt)
        memory_observation = f"Tool Observation: {initial_memories}"
        history.append({"role": "system", "content": memory_observation})
        scratchpad.append({"type": "observation", "content": memory_observation, "timestamp": time.time()})

    history.append({"role": "user", "content": user_prompt})
    scratchpad.append({"type": "user_prompt", "content": user_prompt, "timestamp": time.time()})

    max_turns = 5
    for turn in range(max_turns):
        current_span = trace.get_current_span()
        current_span.set_attribute("react.turn", turn)

        # 1. Build the prompt for QuantumPulse
        full_prompt_messages = [QPChatMessage(**msg) for msg in history]
        full_prompt_messages.append(QPChatMessage(role="system", content=SYSTEM_PROMPT.format(tools=toolbox.get_tool_descriptions())))
        
        # 2. Call QuantumPulse
        request = QPChatRequest(model=llm_config['model'], messages=full_prompt_messages)
        response = asyncio.run(qpulse_client.get_chat_completion(request))
        response_text = response.choices[0].message.content
        history.append({"role": "assistant", "content": response_text})

        # 3. Parse the response and STREAM THE THOUGHT
        try:
            thought = response_text.split("Action:")[0].replace("Thought:", "").strip()
            
            # --- Stream the thought to Pulsar ---
            if thoughts_producer:
                thought_message = {
                    "conversation_id": conversation_id,
                    "thought": thought,
                    "timestamp": int(time.time() * 1000)
                }
                buf = io.BytesIO()
                fastavro.writer(buf, THOUGHT_SCHEMA, [thought_message])
                thoughts_producer.send_async(buf.getvalue(), callback=lambda res, msg_id: None)
            # ------------------------------------

            action_str = response_text.split("Action:")[1].strip()
            action_json = json.loads(action_str)
            current_span.add_event("LLM Response Parsed", {"thought": thought, "action": json.dumps(action_json)})
            scratchpad.append({"type": "thought", "content": thought, "timestamp": time.time()})
            scratchpad.append({"type": "action", "content": action_json, "timestamp": time.time()})
        except (IndexError, json.JSONDecodeError) as e:
            logger.error("Could not parse LLM response", response=response_text, error=str(e))
            scratchpad.append({"type": "error", "content": "Could not parse LLM response.", "timestamp": time.time()})
            context_manager.append_to_history(conversation_id, history, scratchpad)
            
            # --- Reflexion Step on Failure ---
            generate_and_save_reflexion(user_prompt, scratchpad, context_manager, qpulse_client, llm_config)
            
            return "Error: Could not parse my own action. I will try again."

        # 4. Execute the action
        if action_json.get("action") == "finish":
            final_answer = action_json.get("answer", "No answer provided.")
            
            # --- Memory Creation Step ---
            try:
                logger.info("Conversation finished. Generating structured memory.")
                
                # New prompt to ask the LLM for a structured memory object
                memory_prompt = f"""
                Based on our entire conversation, generate a structured JSON object for my long-term memory.
                The JSON object must conform to the following schema:
                {{
                    "agent_id": "{prompt_data.get('agent_id')}",
                    "conversation_id": "{conversation_id}",
                    "summary": "A concise, one-paragraph summary of the key facts, findings, and conclusions.",
                    "entities": ["A list of key entities involved (e.g., service names, technologies, people)."],
                    "key_relationships": {{
                        "entity_1": ["relationship_1_to_entity_2", "relationship_2_to_entity_3"],
                        "entity_2": ["relationship_3_to_entity_4"]
                    }},
                    "outcome": "The final outcome of the task. Choose from: 'SUCCESSFULLY_RESOLVED', 'FAILED_NEEDS_INFO', 'NO_ACTION_NEEDED'.",
                    "full_prompt": "{user_prompt}",
                    "final_answer": "{final_answer}"
                }}

                Conversation History:
                {json.dumps(history, indent=2)}

                Respond with ONLY the valid JSON object.
                """
                
                memory_request_messages = [QPChatMessage(role="system", content=memory_prompt)]
                memory_request = QPChatRequest(model=llm_config['model'], messages=memory_request_messages, temperature=0.2)
                
                memory_response = asyncio.run(qpulse_client.get_chat_completion(memory_request))
                memory_json_str = memory_response.choices[0].message.content
                
                # The LLM should return a JSON string, which we parse into a dict
                memory_data = json.loads(memory_json_str)
                
                if memory_data:
                    logger.info("Saving structured memory.", memory_id=memory_data.get('memory_id'))
                    toolbox.execute_tool("save_memory", memory=memory_data)
            except Exception as e:
                logger.error("Failed to generate and save structured memory.", error=str(e), exc_info=True)

            context_manager.append_to_history(conversation_id, history, scratchpad)
            return final_answer
        elif action_json.get("action") == "call_tool":
            tool_name = action_json.get("tool_name")
            parameters = action_json.get("parameters", {})
            logger.info("Executing tool", tool_name=tool_name, parameters=parameters)
            observation = toolbox.execute_tool(tool_name, context_manager=context_manager, **parameters)
            observation_text = f"Tool Observation: {observation}"
            history.append({"role": "system", "content": observation_text})
            scratchpad.append({"type": "observation", "content": observation_text, "timestamp": time.time()})
        else:
            observation_text = "Error: Invalid action specified."
            history.append({"role": "system", "content": observation_text})
            scratchpad.append({"type": "error", "content": observation_text, "timestamp": time.time()})

    logger.warning("Reached max turns without a final answer.", conversation_id=conversation_id)
    scratchpad.append({"type": "error", "content": "Reached max turns.", "timestamp": time.time()})
    context_manager.append_to_history(conversation_id, history, scratchpad)

    # --- Reflexion Step on Failure ---
    generate_and_save_reflexion(user_prompt, scratchpad, context_manager, qpulse_client, llm_config)

    return "Error: Reached maximum turns without a final answer."

# --- Agent Setup ---

def setup_default_agent(config: dict):
    """Sets up the toolbox and context for the default agent."""
    logger.info("Setting up default agent...")
    toolbox = Toolbox()
    
    services_config = config.get('services', {})

    # Pass the service URLs to the tools that need them
    toolbox.register_tool(Tool(
        name=vectorstore_tool.name,
        description=vectorstore_tool.description,
        func=vectorstore_tool.func,
        config=services_config
    ))
    toolbox.register_tool(human_tool) # Does not require config
    toolbox.register_tool(Tool(
        name=integrationhub_tool.name,
        description=integrationhub_tool.description,
        func=integrationhub_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=knowledgegraph_tool.name,
        description=knowledgegraph_tool.description,
        func=knowledgegraph_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=summarize_activity_tool.name,
        description=summarize_activity_tool.description,
        func=summarize_activity_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=find_experts_tool.name,
        description=find_experts_tool.description,
        func=find_experts_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=quantumpulse_tool.name,
        description=quantumpulse_tool.description,
        func=quantumpulse_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=save_memory_tool.name,
        description=save_memory_tool.description,
        func=save_memory_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=search_memory_tool.name,
        description=search_memory_tool.description,
        func=search_memory_tool.func,
        config=services_config
    ))
    toolbox.register_tool(github_tool) # Requires more specific config, handle later
    toolbox.register_tool(generate_table_tool) # Does not require config
    toolbox.register_tool(list_tools_tool)
    toolbox.register_tool(Tool(
        name=trigger_dag_tool.name,
        description=trigger_dag_tool.description,
        func=trigger_dag_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=get_dag_status_tool.name,
        description=get_dag_status_tool.description,
        func=get_dag_status_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=delegation_tool.name,
        description=delegation_tool.description,
        func=delegation_tool.func,
        config=services_config
    ))
    toolbox.register_tool(Tool(
        name=code_search_tool.name,
        description=code_search_tool.description,
        func=code_search_tool.func,
        config=services_config
    ))
    return toolbox

def run_agent():
    config = load_config()
    pulsar_config = config['pulsar']
    llm_config = config['llm']
    
    setup_agent_memory()

    # --- Personality Selection ---
    personality = os.environ.get("AGENT_PERSONALITY", "default")
    
    if personality == "devops":
        agent_id = DEVOPS_AGENT_ID
        task_topic = DEVOPS_TASK_TOPIC
        system_prompt = DEVOPS_SYSTEM_PROMPT
        toolbox, context_manager = setup_devops_agent(config)
    elif personality == "data_analyst":
        agent_id = DA_AGENT_ID
        task_topic = DA_TASK_TOPIC
        system_prompt = DATA_ANALYST_SYSTEM_PROMPT
        toolbox, context_manager = setup_data_analyst_agent(config)
    elif personality == "knowledge_engineer":
        agent_id = KE_AGENT_ID
        task_topic = KE_TASK_TOPIC
        system_prompt = KNOWLEDGE_ENGINEER_SYSTEM_PROMPT
        toolbox, context_manager = setup_knowledge_engineer_agent(config)
    elif personality == "predictive_analyst":
        agent_id = PA_AGENT_ID
        task_topic = PA_TASK_TOPIC
        system_prompt = PREDICTIVE_ANALYST_SYSTEM_PROMPT
        toolbox, context_manager = setup_predictive_analyst_agent(config)
    elif personality == "docs_agent":
        agent_id = DOCS_AGENT_ID
        task_topic = DOCS_TASK_TOPIC
        system_prompt = DOCS_AGENT_SYSTEM_PROMPT
        toolbox, context_manager = setup_docs_agent(config)
    else: # Default personality
        agent_id = f"agentq-default-{uuid.uuid4()}"
        task_topic = f"persistent://public/default/q.agentq.tasks.{agent_id}"
        system_prompt = SYSTEM_PROMPT
        toolbox = setup_default_agent(config)
        context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=agent_id)
        context_manager.connect()

    # The rest of the agent runs the same, regardless of personality
    
    pulsar_client = None
    try:
        # The agent no longer needs direct access to secrets.
        # It interacts with other services that handle their own auth.
        qpulse_client = QuantumPulseClient(base_url=config['qpulse_url'])
        pulsar_client = pulsar.Client(pulsar_config['service_url'])
        context_manager.connect()

        # Producer for registration
        reg_producer = pulsar_client.create_producer(pulsar_config['registration_topic'], schema=pulsar.schema.BytesSchema())
        register_with_manager(reg_producer, agent_id, task_topic)
        reg_producer.close()
        
        # Consumer for dedicated tasks
        consumer = pulsar_client.subscribe(task_topic, subscription_name)
        
        # Producer for results
        result_producer = pulsar_client.create_producer(pulsar_config['results_topic'], schema=pulsar.schema.BytesSchema())
        # Producer for thoughts
        thoughts_producer = pulsar_client.create_producer(pulsar_config['thoughts_topic'], schema=pulsar.schema.BytesSchema())
        
        # This span will be the parent for all processing spans inside the loop
        with tracer.start_as_current_span("agent_main_loop") as parent_span:
            parent_span.set_attribute("agent.id", agent_id)
            parent_span.set_attribute("agent.personality", personality)
            parent_span.set_attribute("agent.task_topic", task_topic)
            logger.info("Agent running", agent_id=agent_id, personality=personality, topic=task_topic)

            while running:
                try:
                    msg = consumer.receive(timeout_millis=1000)
                    bytes_reader = io.BytesIO(msg.data())
                    prompt_data = next(fastavro.reader(bytes_reader, PROMPT_SCHEMA), None)
                    if not prompt_data:
                        consumer.acknowledge(msg)
                        continue

                    logger.info("Received task", task_id=prompt_data.get("id"), workflow_id=prompt_data.get("workflow_id"))
                    final_result = react_loop(prompt_data, context_manager, toolbox, qpulse_client, llm_config, thoughts_producer)
                    
                    # Publish the final result
                    result_message = {
                        "id": prompt_data.get("id"), 
                        "result": final_result, 
                        "llm_model": llm_config['model'], 
                        "prompt": prompt_data.get("prompt"),
                        "timestamp": int(time.time() * 1000),
                        "workflow_id": prompt_data.get("workflow_id"),
                        "task_id": prompt_data.get("task_id"),
                        "agent_personality": personality
                    }
                    buf = io.BytesIO()
                    fastavro.writer(buf, RESULT_SCHEMA, [result_message])
                    result_producer.send(buf.getvalue())
                    logger.info("Published result", task_id=prompt_data.get("id"), workflow_id=prompt_data.get("workflow_id"))

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
        shared_pulsar_client.close()
        context_manager.close()
        logger.info("Agent has shut down", agent_id=agent_id)

def shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received. Stopping agent gracefully...")
    running = False

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    run_agent()
