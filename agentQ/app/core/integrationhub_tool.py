import logging
import httpx
import asyncio
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
INTEGRATION_HUB_URL = "http://localhost:8000" # Port for IntegrationHub

# --- Tool Definition ---

def trigger_integration_flow(flow_id: str, parameters: Dict[str, Any] = None, config: Dict[str, Any] = None) -> str:
    """
    Triggers a pre-defined flow in the IntegrationHub.
    Use this to perform actions in external systems like sending emails,
    posting messages to Slack, or creating calendar events.
    
    Args:
        flow_id (str): The unique ID of the flow to trigger.
        parameters (dict): A dictionary of parameters to pass to the flow.
        
    Returns:
        A confirmation message indicating success or failure.
    """
    try:
        integration_hub_url = config.get("integration_hub_url")
        if not integration_hub_url:
            return "Error: integration_hub_url not found in tool configuration."

        url = f"{integration_hub_url}/flows/{flow_id}/trigger"
        
        # httpx is async, so we need to run it in an event loop
        async def do_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=parameters or {}, timeout=30.0)
                response.raise_for_status()
                return response.json()
        
        response_data = asyncio.run(do_request())
        
        logger.info(f"Successfully triggered IntegrationHub flow '{flow_id}'. Response: {response_data}")
        return f"Successfully triggered flow '{flow_id}'. Status: {response_data.get('status')}"

    except httpx.HTTPStatusError as e:
        error_details = e.response.json().get("detail", e.response.text)
        logger.error(f"Error triggering IntegrationHub flow '{flow_id}': {e.response.status_code} - {error_details}")
        return f"Error: Failed to trigger flow '{flow_id}'. Status: {e.response.status_code}. Detail: {error_details}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while triggering flow '{flow_id}': {e}", exc_info=True)
        return f"Error: An unexpected error occurred: {e}"


# --- Tool Registration Object ---

integrationhub_tool = Tool(
    name="trigger_integration_flow",
    description="Triggers a named, pre-configured workflow in the IntegrationHub to perform an action in an external system (e.g., send an email, post to Slack). You must know the 'flow_id' and the required 'parameters' for the flow.",
    func=trigger_integration_flow
) 