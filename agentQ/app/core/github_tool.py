import logging
import httpx
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# --- Configuration ---
INTEGRATION_HUB_URL = "http://localhost:8000"

def comment_on_pr(repo: str, pr_number: int, comment: str) -> str:
    """
    Posts a comment to a specific GitHub pull request.

    Args:
        repo (str): The repository name in 'owner/repo' format (e.g., 'my-org/my-project').
        pr_number (int): The number of the pull request.
        comment (str): The content of the comment to post.
    
    Returns:
        A string containing the result of the operation.
    """
    try:
        url = f"{INTEGRATION_HUB_URL}/api/v1/flows/post_comment_on_pr/trigger"
        
        # This assumes the IntegrationHub is secured and requires a token.
        # The agent needs a mechanism to get a valid service account token.
        # For now, this is simplified.
        # TODO: Implement a secure way for the agent to get its own service token.
        headers = {"Authorization": "Bearer YOUR_AGENT_SERVICE_TOKEN"}
        
        payload = {
            "parameters": {
                "repo": repo,
                "pr_number": pr_number,
                "body": comment,
            }
        }
        
        with httpx.Client() as client:
            response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
        
        logger.info(f"Successfully triggered flow to comment on PR #{pr_number} in repo {repo}")
        return f"Successfully posted comment to PR #{pr_number}."

    except httpx.HTTPStatusError as e:
        error_details = e.response.json().get("detail", e.response.text)
        logger.error(f"Error triggering GitHub flow: {e.response.status_code} - {error_details}")
        return f"Error: Failed to post comment. Status: {e.response.status_code}. Detail: {error_details}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling IntegrationHub: {e}", exc_info=True)
        return f"Error: An unexpected error occurred: {e}"


# --- Tool Registration ---

github_tool = Tool(
    name="comment_on_pr",
    description="Posts a comment to a specific GitHub pull request. Useful for providing feedback, summaries, or review results.",
    func=comment_on_pr
)
