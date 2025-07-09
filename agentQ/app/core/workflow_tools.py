import logging
import httpx
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
MANAGER_URL = "http://localhost:8003" # managerQ's default port

def update_shared_context(workflow_id: str, updates: Dict[str, Any]) -> str:
    """
    Updates the shared context for a given workflow.
    Use this to share findings, status, or intermediate results with other agents
    working on the same goal.

    Args:
        workflow_id (str): The ID of the current workflow.
        updates (Dict[str, Any]): A dictionary of key-value pairs to add or update in the shared context.

    Returns:
        A string confirming the result of the operation.
    """
    logger.info(f"Updating shared context for workflow '{workflow_id}' with: {updates}")
    endpoint = f"{MANAGER_URL}/v1/workflows/{workflow_id}/context"
    try:
        with httpx.Client() as client:
            response = client.patch(endpoint, json=updates)
            response.raise_for_status()
        return "Shared context updated successfully."
    except httpx.HTTPStatusError as e:
        error_details = e.response.json().get("detail", e.response.text)
        return f"Error: Failed to update shared context. Status: {e.response.status_code}. Detail: {error_details}"
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"


def read_shared_context(workflow_id: str) -> str:
    """
    Reads the full shared context for a given workflow.
    Use this to get the latest information and findings from other agents
    working on the same goal before you start your own task.

    Args:
        workflow_id (str): The ID of the current workflow.

    Returns:
        A JSON string representation of the shared context.
    """
    logger.info(f"Reading shared context for workflow '{workflow_id}'")
    endpoint = f"{MANAGER_URL}/v1/workflows/{workflow_id}/context"
    try:
        with httpx.Client() as client:
            response = client.get(endpoint)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_details = e.response.json().get("detail", e.response.text)
        return f"Error: Failed to read shared context. Status: {e.response.status_code}. Detail: {error_details}"
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"


# --- Tool Registration ---

update_context_tool = Tool(
    name="update_shared_context",
    description="Updates the shared 'whiteboard' for the current workflow with a dictionary of new information. Use this to share findings with other agents.",
    func=update_shared_context,
)

read_context_tool = Tool(
    name="read_shared_context",
    description="Reads the entire shared 'whiteboard' for the current workflow to get the latest findings from other agents.",
    func=read_shared_context,
) 