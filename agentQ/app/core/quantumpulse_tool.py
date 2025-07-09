import logging
import httpx
import asyncio
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
MANAGERQ_URL = "http://localhost:8003" # The API for the agent manager

# --- Tool Definition ---

def delegate_to_quantumpulse(prompt: str, config: Dict[str, Any] = None) -> str:
    """
    Delegates a complex prompt, a "what-if" scenario, or a request for deep reasoning
    to the QuantumPulse inference service. Use this when a question is too complex
    to be answered by a simple knowledge base search.
    
    Args:
        prompt (str): The detailed prompt or question to send.
        
    Returns:
        The final synthesized result from the QuantumPulse service.
    """
    try:
        manager_url = config.get("manager_url")
        if not manager_url:
            return "Error: manager_url not found in tool configuration."
            
        url = f"{manager_url}/v1/tasks"
        
        async def do_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"prompt": prompt}, timeout=120.0) # Longer timeout for inference
                response.raise_for_status()
                return response.json()
        
        response_data = asyncio.run(do_request())
        
        logger.info(f"Successfully delegated task to QuantumPulse. Result: {response_data.get('result')}")
        return response_data.get("result", "Error: No result returned from the service.")

    except httpx.HTTPStatusError as e:
        error_details = e.response.json().get("detail", e.response.text)
        logger.error(f"Error delegating to QuantumPulse: {e.response.status_code} - {error_details}")
        return f"Error: Failed to delegate task. Status: {e.response.status_code}. Detail: {error_details}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while delegating to QuantumPulse: {e}", exc_info=True)
        return f"Error: An unexpected error occurred: {e}"


# --- Tool Registration Object ---

quantumpulse_tool = Tool(
    name="delegate_to_quantumpulse",
    description="For complex questions, 'what-if' scenarios, or requests that require deep, synthesized reasoning beyond simple document retrieval, delegate the task to the powerful QuantumPulse inference service.",
    func=delegate_to_quantumpulse
) 