import logging
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader

from app.core.context import context_manager
from app.core.rag import rag_module
from app.core.config import get_config
from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import InferenceRequest
from app.services.pulsar_client import h2m_pulsar_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Prompt Templating Setup ---
# A more robust approach would be to have a dedicated templates directory
PROMPT_TEMPLATE = """
System: You are a helpful and professional AI assistant. Answer the user's question based on the provided context. If the context is not relevant or does not contain the answer, say that you do not have enough information to answer. Do not make up information.

{% if rag_context %}
--- CONTEXT ---
{{ rag_context }}
--- END CONTEXT ---
{% endif %}

{% for message in history %}
{{ message.role | title }}: {{ message.content }}
{% endfor %}
User: {{ user_query }}
Assistant:
"""
jinja_env = Environment()
prompt_template = jinja_env.from_string(PROMPT_TEMPLATE)


class ConversationOrchestrator:
    """
    Orchestrates the entire process of handling a user's message.
    """

    def __init__(self):
        services_config = get_config().services
        self.qp_client = QuantumPulseClient(base_url=services_config.quantumpulse_url)

    async def handle_message(self, user_id: str, text: str, conversation_id: str = None) -> (str, str):
        """
        The main method to process a user's message and get a response.

        Args:
            user_id: The unique ID of the authenticated user.
            text: The user's input message.
            conversation_id: The existing conversation ID, if any.

        Returns:
            A tuple containing the final AI response text and the conversation ID.
        """
        logger.info(f"Orchestrator: Handling message for user '{user_id}' in conversation '{conversation_id}'")

        # 1. Get conversation history
        conv_id, history = await context_manager.get_or_create_conversation_history(user_id, conversation_id)

        # 2. Get RAG context
        rag_context = await rag_module.retrieve_context(text)

        # 3. Construct the final prompt
        final_prompt = self._build_prompt(text, history, rag_context)

        # 4. Create a temporary topic for the reply
        reply_topic, consumer = await h2m_pulsar_client.create_consumer_for_reply()

        try:
            # 5. Submit to QuantumPulse for inference, telling it where to reply
            inference_request = InferenceRequest(
                prompt=final_prompt,
                conversation_id=conv_id,
                reply_to_topic=reply_topic
            )
            request_id = await self.qp_client.submit_inference(inference_request)
            logger.info(f"Submitted inference request {request_id}. Waiting for response on {reply_topic}.")

            # 6. Wait for the real response
            response_msg = await h2m_pulsar_client.await_response(consumer)
            ai_response_text = response_msg.value().text
            
            # 7. Acknowledge the message
            consumer.acknowledge(response_msg)
            logger.info(f"Received real-time response for request {request_id}.")

        finally:
            # 8. Clean up the temporary consumer
            consumer.close()

        # 9. Save the new turn to the conversation history
        await context_manager.add_message_to_history(user_id, conv_id, text, ai_response_text)
        
        logger.info(f"Orchestrator: Successfully handled message for conversation {conv_id}")
        return ai_response_text, conv_id

    def _build_prompt(self, user_query: str, history: List[Dict], rag_context: str) -> str:
        """
        Builds the final prompt to be sent to the language model using Jinja2.
        """
        prompt = prompt_template.render(
            rag_context=rag_context,
            history=history,
            user_query=user_query
        )
        logger.debug(f"Constructed final prompt:\n{prompt}")
        return prompt

# Global instance for the application
orchestrator = ConversationOrchestrator() 