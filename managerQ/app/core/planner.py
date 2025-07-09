import logging
import json
import asyncio
from typing import Dict, Any

from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import QPChatRequest, QPChatMessage
from managerQ.app.models import Workflow
from managerQ.app.config import settings

logger = logging.getLogger(__name__)

# This client will be configured with the URL from settings
q_pulse_client = QuantumPulseClient(base_url=settings.qpulse_url)


PLANNER_SYSTEM_PROMPT = """
You are an expert planner and task decomposition AI. Your role is to analyze a user's request and break it down into a structured workflow of tasks that can be executed by other AI agents.

The user's request will be provided to you. You must respond with ONLY a single, valid JSON object that adheres to the `Workflow` schema.

**Workflow Schema:**
- `original_prompt`: The user's original request.
- `tasks`: A list of `WorkflowTask` objects.
    - `task_id`: A unique identifier for the task (e.g., "task_1", "task_2").
    - `agent_personality`: The type of agent best suited for this task. Choose from: 'default', 'devops', 'data_analyst'.
    - `prompt`: A clear, specific prompt for the agent that will execute this task.
    - `dependencies`: A list of `task_id`s that must be completed before this task can start. An empty list means the task can start immediately.

**Key Instructions:**
- If the request is simple and can be handled by a single agent in one step, create a workflow with a single task and no dependencies.
- If the request requires multiple steps or specialists, create a directed acyclic graph (DAG) of tasks using the `dependencies` field.
- Ensure the `agent_personality` is appropriate for the task's prompt. For example, use 'devops' for infrastructure or monitoring tasks, and 'data_analyst' for data-related queries.
- Make the task prompts clear and self-contained. Assume the agent executing the task has no knowledge of the overall workflow.

**Example Request:**
"Analyze the performance impact of the last release and summarize user feedback."

**Example JSON Response:**
{
  "original_prompt": "Analyze the performance impact of the last release and summarize user feedback.",
  "tasks": [
    {
      "task_id": "task_1",
      "agent_personality": "devops",
      "prompt": "Gather and summarize the key performance metrics (CPU, memory, latency) for all services for 24 hours before and after the deployment of release v1.2.3.",
      "dependencies": []
    },
    {
      "task_id": "task_2",
      "agent_personality": "data_analyst",
      "prompt": "Query the user feedback data from the 'human-feedback' MinIO bucket and provide a summary of user sentiment ('good' vs 'bad') for the 24 hours following the release of v1.2.3.",
      "dependencies": []
    },
    {
      "task_id": "task_3",
      "agent_personality": "default",
      "prompt": "Synthesize the following performance analysis and user feedback summary into a final report. Performance data: {{task_1.result}}. Feedback summary: {{task_2.result}}.",
      "dependencies": ["task_1", "task_2"]
    }
  ]
}
"""

class Planner:
    """
    Uses an LLM to decompose a user prompt into a structured workflow.
    """
    def create_plan(self, user_prompt: str) -> Workflow:
        """
        Generates a workflow plan from a user prompt.
        """
        logger.info(f"Creating a plan for prompt: '{user_prompt}'")
        
        # The prompt for the planner is a combination of the system prompt and the user request.
        full_prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n**User Request:**\n{user_prompt}"
        
        try:
            # Use the shared QuantumPulse client to make the call.
            messages = [QPChatMessage(role="user", content=full_prompt)]
            request = QPChatRequest(
                model="gpt-4-turbo", # A powerful model is needed for planning
                messages=messages,
                max_tokens=2048
            )
            
            # Since create_plan is synchronous, we use asyncio.run
            response = asyncio.run(q_pulse_client.get_chat_completion(request))
            
            # The response from the LLM should be a JSON string
            plan_json_str = response.choices[0].message.content
            plan_json = json.loads(plan_json_str)
            workflow = Workflow(**plan_json)
            logger.info(f"Successfully created workflow '{workflow.workflow_id}' with {len(workflow.tasks)} tasks.")
            return workflow

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode or validate the LLM's plan response: {e}", exc_info=True)
            raise ValueError("The planner failed to create a valid workflow JSON.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while creating a plan: {e}", exc_info=True)
            raise

# Singleton instance
planner = Planner() 