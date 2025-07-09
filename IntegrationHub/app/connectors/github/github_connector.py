import logging
from typing import Dict, Any, Optional
from github import Github, GithubException
from fastapi import HTTPException
import httpx

from app.models.connector import BaseConnector, ConnectorAction
from app.core.vault_client import vault_client

logger = logging.getLogger(__name__)

class GitHubConnector(BaseConnector):
    """
    A connector for interacting with the GitHub API.
    """

    @property
    def connector_id(self) -> str:
        return "github"

    async def _get_client(self, credential_id: str) -> Github:
        """Helper to get an authenticated PyGithub client."""
        credential = await vault_client.get_credential(credential_id)
        # The PAT should be stored in Vault with the key 'personal_access_token'
        pat = credential.secrets.get("personal_access_token")
        if not pat:
            raise ValueError("GitHub PAT not found in credential secrets.")
        return Github(pat)

    async def execute(self, action: ConnectorAction, configuration: Dict[str, Any], data_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = await self._get_client(action.credential_id)
        
        try:
            repo_name = configuration["repo"]
            repo = client.get_repo(repo_name)

            if action.action_id == "get_issue_details":
                return self._get_issue_details(repo, configuration)
            elif action.action_id == "create_pull_request_comment":
                return self._create_pr_comment(repo, configuration)
            elif action.action_id == "get_file_contents":
                return self._get_file_contents(repo, configuration)
            elif action.action_id == "get_pr_diff":
                return await self._get_pr_diff(repo, configuration)
            else:
                raise ValueError(f"Unsupported action for GitHub connector: {action.action_id}")

        except GithubException as e:
            logger.error(f"GitHub API error: {e.status} - {e.data}")
            raise HTTPException(status_code=e.status, detail=e.data)
        except Exception as e:
            logger.error(f"An unexpected error occurred in GitHubConnector: {e}", exc_info=True)
            raise

    def _get_issue_details(self, repo, config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches details for a specific issue."""
        issue_number = config["issue_number"]
        issue = repo.get_issue(number=issue_number)
        return {
            "title": issue.title, "state": issue.state, "body": issue.body,
            "labels": [label.name for label in issue.labels],
            "url": issue.html_url
        }

    def _create_pr_comment(self, repo, config: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a comment on a pull request."""
        pr_number = config["pr_number"]
        comment_body = config["body"]
        pr = repo.get_pull(number=pr_number)
        comment = pr.create_issue_comment(comment_body)
        return {"comment_id": comment.id, "url": comment.html_url}

    def _get_file_contents(self, repo, config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches the contents of a file from the repository."""
        file_path = config["path"]
        ref = config.get("ref", "main") # Default to main branch
        file_content = repo.get_contents(file_path, ref=ref)
        return {"content": file_content.decoded_content.decode("utf-8")}

    async def _get_pr_diff(self, repo, config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches the raw diff for a pull request."""
        pr_number = config["pr_number"]
        pr = repo.get_pull(number=pr_number)
        
        # The diff content is not available directly via the PyGithub object.
        # We must make a separate HTTP request to the diff_url.
        diff_url = pr.diff_url
        async with httpx.AsyncClient() as client:
            response = await client.get(diff_url, timeout=30.0)
            response.raise_for_status()
            return {"diff": response.text}


# Instantiate a single instance
github_connector = GitHubConnector()
