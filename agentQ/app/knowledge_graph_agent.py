# agentQ/app/knowledge_graph_agent.py
import logging
import threading
import pulsar
import io
import time
import json
import fastavro

from agentQ.app.core.toolbox import Toolbox
from agentQ.app.core.knowledgegraph_tool import text_to_gremlin_tool
from agentQ.app.core.prompts import KNOWLEDGE_GRAPH_PROMPT_TEMPLATE
from agentQ.app.main import react_loop, register_with_manager
from shared.q_messaging_schemas.schemas import PROMPT_SCHEMA, RESULT_SCHEMA

logger = logging.getLogger(__name__)

AGENT_ID = "knowledge_graph_agent"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"
REGISTRATION_TOPIC = "persistent://public/default/q.managerq.agent.registrations"

def run_knowledge_graph_agent(pulsar_client, qpulse_client, llm_config, context_manager):
    """
    The main function for the Knowledge Graph agent.
    """
    logger.info("Starting Knowledge Graph Agent...")
    
    kg_toolbox = Toolbox()
    kg_toolbox.register_tool(text_to_gremlin_tool)

    registration_producer = pulsar_client.create_producer(REGISTRATION_TOPIC)
    result_producer = pulsar_client.create_producer(llm_config['result_topic'])
    
    register_with_manager(registration_producer, AGENT_ID, TASK_TOPIC)
    
    consumer = pulsar_client.subscribe(TASK_TOPIC, f"agentq-sub-{AGENT_ID}")

    def consumer_loop():
        while True:
            try:
                msg = consumer.receive(timeout_millis=1000)
                bytes_reader = io.BytesIO(msg.data())
                prompt_data = next(fastavro.reader(bytes_reader, PROMPT_SCHEMA))
                
                final_result = react_loop(
                    prompt_data, 
                    context_manager, 
                    kg_toolbox, 
                    qpulse_client, 
                    llm_config, 
                    None,
                    KNOWLEDGE_GRAPH_PROMPT_TEMPLATE
                )
                
                result_message = {
                    "id": prompt_data.get("id"),
                    "result": final_result,
                    "llm_model": llm_config.get('model'),
                    "prompt": prompt_data.get("prompt"),
                    "timestamp": int(time.time() * 1000),
                    "workflow_id": prompt_data.get("workflow_id"),
                    "task_id": prompt_data.get("task_id"),
                    "agent_personality": AGENT_ID
                }
                buf = io.BytesIO()
                fastavro.writer(buf, RESULT_SCHEMA, [result_message])
                result_producer.send(buf.getvalue())
                
                consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in KG agent loop: {e}", exc_info=True)

    threading.Thread(target=consumer_loop, daemon=True).start()
    logger.info("Knowledge Graph Agent consumer thread started.") 