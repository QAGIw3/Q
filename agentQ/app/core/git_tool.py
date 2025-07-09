import logging
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool
from agentQ.app.core.integrationhub_tool import trigger_integration_flow

logger = logging.getLogger(__name__)

def propose_code_fix(
    repo: str, 
    file_path: str,
    new_content: str,
    commit_message: str,
    pr_title: str,
    pr_body: str,
    new_branch_name: str,
    source_branch_name: str = "main",
    config: Dict[str, Any] = None
) -> str:
    """
    Proposes a code fix by creating a branch, committing a change, and opening a pull request.

    Args:
        repo (str): The repository name in 'owner/repo' format.
        file_path (str): The full path to the file to be changed.
        new_content (str): The full new content of the file.
        commit_message (str): The message for the git commit.
        pr_title (str): The title for the pull request.
        pr_body (str): The description for the pull request.
        new_branch_name (str): The name for the new branch.
        source_branch_name (str): The branch to branch off of (defaults to 'main').
        config (Dict[str, Any]): The agent's service configuration.

    Returns:
        A string containing the result of the operation, including the PR URL.
    """
    logger.info(f"Proposing code fix for '{file_path}' in repo '{repo}'.")
    
    flow_id = "propose_code_fix"
    parameters = {
        "repo": repo,
        "file_path": file_path,
        "new_content": new_content,
        "commit_message": commit_message,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "new_branch_name": new_branch_name,
        "source_branch_name": source_branch_name,
    }
    
    # Re-use the existing integration hub tool to trigger the flow
    return trigger_integration_flow(flow_id, parameters, config)

# --- Tool Registration ---
propose_code_fix_tool = Tool(
    name="propose_code_fix",
    description="Proposes a code change by creating a new branch, committing a file modification, and opening a GitHub pull request for review. Use this to suggest fixes for bugs you have identified.",
    func=propose_code_fix
) 