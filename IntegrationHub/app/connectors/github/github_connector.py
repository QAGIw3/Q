import logging
from typing import Dict, Any, Optional
from github import Github, GithubException
from fastapi import HTTPException
import httpx
import asyncio

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

            action_map = {
                "get_issue_details": self._get_issue_details,
                "create_pull_request_comment": self._create_pr_comment,
                "get_file_contents": self._get_file_contents,
                "get_pr_diff": self._get_pr_diff,
                "create_branch": self._create_branch,
                "create_commit": self._create_commit,
                "create_pull_request": self._create_pull_request,
            }

            if action.action_id in action_map:
                # Some methods are async, some are not due to library limitations.
                # We handle this by checking if the function is a coroutine.
                func = action_map[action.action_id]
                if asyncio.iscoroutinefunction(func):
                    return await func(repo, configuration)
                else:
                    return func(repo, configuration)
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

    def _create_branch(self, repo, config: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new branch from a source branch."""
        new_branch_name = config["new_branch_name"]
        source_branch_name = config.get("source_branch_name", "main")
        
        source_branch = repo.get_branch(source_branch_name)
        ref = repo.create_git_ref(
            ref=f"refs/heads/{new_branch_name}",
            sha=source_branch.commit.sha
        )
        logger.info(f"Created branch '{new_branch_name}' in repo '{repo.full_name}'.")
        return {"branch_name": new_branch_name, "ref": ref.ref, "sha": ref.object.sha}

    def _create_commit(self, repo, config: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a commit by updating a file on a specific branch."""
        file_path = config["file_path"]
        commit_message = config["commit_message"]
        new_content = config["new_content"]
        branch_name = config["branch_name"]
        
        try:
            # Try to get the file to update it
            file_contents = repo.get_contents(file_path, ref=branch_name)
            commit_result = repo.update_file(
                path=file_path,
                message=commit_message,
                content=new_content,
                sha=file_contents.sha,
                branch=branch_name
            )
        except GithubException as e:
            if e.status == 404: # File doesn't exist, create it
                commit_result = repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=new_content,
                    branch=branch_name
                )
            else:
                raise # Re-raise other errors
        
        logger.info(f"Created commit '{commit_message}' on branch '{branch_name}'.")
        return {"commit_sha": commit_result['commit'].sha, "path": file_path}

    def _create_pull_request(self, repo, config: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a pull request."""
        title = config["title"]
        body = config["body"]
        head_branch = config["head_branch"]
        base_branch = config.get("base_branch", "main")
        
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch
        )
        logger.info(f"Created pull request '{title}' from '{head_branch}' to '{base_branch}'.")
        return {"pr_number": pr.number, "url": pr.html_url}

# Instantiate a single instance
github_connector = GitHubConnector()
