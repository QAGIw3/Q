import logging
from typing import Dict, List

from app.core.context import context_manager
from app.core.rag import rag_module
from app.core.config import get_config
from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import InferenceRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConversationOrchestrator:
    """
    Orchestrates the entire process of handling a user's message.
    """

    def __init__(self):
        services_config = get_config().services
        self.qp_client = QuantumPulseClient(base_url=services_config.quantumpulse_url)

    async def handle_message(self, text: str, conversation_id: str = None) -> (str, str):
        """
        The main method to process a user's message and get a response.

        Args:
            text: The user's input message.
            conversation_id: The existing conversation ID, if any.

        Returns:
            A tuple containing the final AI response text and the conversation ID.
        """
        logger.info(f"Orchestrator: Handling message for conversation: {conversation_id}")

        # 1. Get conversation history
        conv_id, history = await context_manager.get_or_create_conversation_history(conversation_id)

        # 2. Get RAG context
        rag_context = await rag_module.retrieve_context(text)

        # 3. Construct the final prompt
        final_prompt = self._build_prompt(text, history, rag_context)

        # 4. Submit to QuantumPulse for inference
        # In a real streaming scenario, we would get a request_id and then listen
        # on a WebSocket for the response associated with that ID.
        # Here, we will simulate a response for simplicity.
        inference_request = InferenceRequest(prompt=final_prompt, conversation_id=conv_id)
        request_id = await self.qp_client.submit_inference(inference_request)
        
        # --- Simulation of receiving a response ---
        # In a real system, this part would be handled by a separate process
        # listening on a WebSocket or a Pulsar topic for results.
        logger.info(f"Submitted inference request {request_id}. Simulating response.")
        ai_response_text = f"This is a simulated AI response to your query about '{text[:30]}...' based on the retrieved context."
        # --- End Simulation ---

        # 5. Save the new turn to the conversation history
        await context_manager.add_message_to_history(conv_id, text, ai_response_text)
        
        logger.info(f"Orchestrator: Successfully handled message for conversation {conv_id}")
        return ai_response_text, conv_id

    def _build_prompt(self, user_query: str, history: List[Dict], rag_context: str) -> str:
        """
        Builds the final prompt to be sent to the language model.
        """
        # Simple prompt template
        template = """
You are a helpful AI assistant. Use the following context to answer the user's question.
If the context is not relevant, ignore it and answer based on the conversation history.

--- CONTEXT ---
{rag_context}
--- END CONTEXT ---

--- CONVERSATION HISTORY ---
{history}
--- END CONVERSATION HISTORY ---

User: {user_query}
Assistant:
"""
        
        # Format history for the prompt
        formatted_history = "\n".join([f"{msg['role'].title()}: {msg['content']}" for msg in history])
        
        prompt = template.format(
            rag_context=rag_context if rag_context else "No relevant context found.",
            history=formatted_history if formatted_history else "This is a new conversation.",
            user_query=user_query
        )
        logger.debug(f"Constructed final prompt:\n{prompt}")
        return prompt

# Global instance for the application
orchestrator = ConversationOrchestrator() 