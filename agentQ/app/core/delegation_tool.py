import logging
import httpx
import asyncio
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
# MANAGER_URL = "http://localhost:8003" # managerQ's default port

def delegate_task(agent_personality: str, prompt: str, config: Dict[str, Any]) -> str:
    """
    Delegates a specific task to another, more specialized agent.
    Use this when you encounter a sub-problem that is outside your expertise.
    For example, a 'default' agent can delegate a request to analyze logs to a 'devops' agent.

    Args:
        agent_personality (str): The personality of the agent to delegate to (e.g., 'devops', 'data_analyst').
        prompt (str): The specific, self-contained prompt for the specialist agent.

    Returns:
        The result from the specialist agent.
    """
    logger.info(f"Delegating task to a '{agent_personality}' agent. Prompt: '{prompt[:100]}...'")
    
    manager_url = config.get("manager_url")
    if not manager_url:
        return "Error: manager_url not found in tool configuration."

    endpoint = f"{manager_url}/v1/agent-tasks"
    
    payload = {
        "agent_personality": agent_personality,
        "prompt": prompt
    }
    
    try:
        # This interaction needs to be synchronous from the agent's perspective.
        # The managerQ endpoint will block until it gets a result.
        with httpx.Client(timeout=300.0) as client: # Long timeout for complex delegated tasks
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            
        # The response should contain the final result from the delegated agent
        final_answer = result.get("result", "No result field in response from managerQ.")
        logger.info(f"Received result from delegated task.")
        return final_answer

    except httpx.HTTPStatusError as e:
        error_details = e.response.json().get("detail", e.response.text)
        logger.error(f"Error delegating task: {e.response.status_code} - {error_details}")
        return f"Error: Failed to delegate task. Status: {e.response.status_code}. Detail: {error_details}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during task delegation: {e}", exc_info=True)
        return f"Error: An unexpected error occurred: {e}"


# --- Tool Registration ---

delegation_tool = Tool(
    name="delegate_task",
    description="Delegates a specific, self-contained task to a specialist agent when a problem is outside your expertise. Specify the required 'agent_personality' and the 'prompt' for that agent.",
    func=delegate_task
) 