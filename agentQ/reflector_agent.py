import logging
from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import QPChatRequest, QPChatMessage
from managerQ.app.models import Workflow
import json

logger = logging.getLogger(__name__)

class ReflectorAgent:
    def __init__(self, qpulse_url: str):
        self.qpulse_client = QuantumPulseClient(base_url=qpulse_url)
        self.reflection_prompt_template = """
You are a Reflector Agent. Your purpose is to analyze a completed workflow to find insights and lessons.
Analyze the following workflow execution record. Identify key successes, failures, and reasons for the outcome.
Formulate a concise 'lesson learned' that can be stored in our knowledge graph to improve future planning.

The lesson should be a single, impactful sentence.

Respond with ONLY a single JSON object with the key "lesson".

Example:
{
  "lesson": "When a service deployment fails, always check the logs of the service that failed to start, not just the deployment tool's logs."
}

Workflow Analysis Request for: {workflow_id}
Original Goal: {original_prompt}
Final Status: {final_status}

Full Workflow Record:
{workflow_dump}
"""

    async def run(self, workflow_json: str) -> str:
        workflow = Workflow(**json.loads(workflow_json))
        
        prompt = self.reflection_prompt_template.format(
            workflow_id=workflow.workflow_id,
            original_prompt=workflow.original_prompt,
            final_status=workflow.status.value,
            workflow_dump=workflow.json(indent=2)
        )
        
        messages = [QPChatMessage(role="user", content=prompt)]
        request = QPChatRequest(model="gpt-4-turbo", messages=messages, max_tokens=512)
        
        response = await self.qpulse_client.get_chat_completion(request)
        
        try:
            lesson_json = json.loads(response.choices[0].message.content)
            return lesson_json['lesson']
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to decode or extract lesson from reflection response: {e}", exc_info=True)
            raise ValueError("Failed to generate a valid lesson.") 