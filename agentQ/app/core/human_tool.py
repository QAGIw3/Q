import logging
import pulsar
import json
from typing import Dict

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
# In a real system, this would come from a shared config
PULSAR_SERVICE_URL = "pulsar://localhost:6650"
HUMAN_FEEDBACK_TOPIC = "persistent://public/default/q.agentq.human_feedback"

# --- Tool Definition ---

def ask_human_for_clarification(question: str, conversation_id: str) -> str:
    """
    Asks a human for clarification or more information when you are stuck.
    
    Args:
        question (str): The specific question you need to ask the human.
        conversation_id (str): The ID of the current conversation, for routing the response.
        
    Returns:
        A confirmation that the question has been sent. The human's response will arrive in a subsequent turn.
    """
    client = None
    producer = None
    try:
        client = pulsar.Client(PULSAR_SERVICE_URL)
        producer = client.create_producer(HUMAN_FEEDBACK_TOPIC)
        
        message_payload = {
            "type": "clarification_request",
            "question": question,
            "conversation_id": conversation_id
        }
        
        producer.send(json.dumps(message_payload).encode('utf-8'))
        logger.info(f"Published human clarification request: {question}")
        
        return f"Your question has been sent to the human: '{question}'. Their response will appear in the conversation history."

    except Exception as e:
        logger.error(f"Failed to ask human for clarification: {e}", exc_info=True)
        return "Error: Could not send the question to the human."
    finally:
        if producer:
            producer.close()
        if client:
            client.close()


# --- Tool Registration Object ---

human_tool = Tool(
    name="ask_human_for_clarification",
    description="When you are stuck, require more information, or need a subjective opinion to proceed, use this tool to ask a human for help. Provide the conversation_id to ensure the response is routed correctly.",
    func=ask_human_for_clarification
) 