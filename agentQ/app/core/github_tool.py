import logging
import httpx
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

# The base URL can be loaded from config
# INTEGRATION_HUB_URL = "http://localhost:8000" 

def comment_on_pr(repo: str, pr_number: int, comment: str, config: Dict[str, Any]) -> str:
    """
    Posts a comment to a specific GitHub pull request.

    Args:
        repo (str): The repository name in 'owner/repo' format (e.g., 'my-org/my-project').
        pr_number (int): The number of the pull request.
        comment (str): The content of the comment to post.
        config (Dict[str, Any]): The agent's configuration dictionary, containing service URLs and tokens.
    
    Returns:
        A string containing the result of the operation.
    """
    try:
        integration_hub_url = config.get('services', {}).get('integrationhub_url', 'http://localhost:8000')
        url = f"{integration_hub_url}/api/v1/flows/post_comment_on_pr/trigger"
        
        service_token = config.get('service_token')
        if not service_token:
            return "Error: Agent is missing its service token for authentication."
            
        headers = {"Authorization": f"Bearer {service_token}"}
        
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
