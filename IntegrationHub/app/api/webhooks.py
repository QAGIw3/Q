from fastapi import APIRouter, Request, HTTPException, Header, Response, status, Depends
from typing import Dict, Any
import hashlib
import hmac
import logging

from ..core.pulsar_client import publish_event
from ..core.engine import engine
from ..core.vault_client import vault_client

logger = logging.getLogger(__name__)
router = APIRouter()

async def verify_github_signature(request: Request, x_hub_signature_256: str = Header(...)):
    """A dependency to verify the webhook signature from GitHub."""
    try:
        # It's critical to get the raw body, not the parsed JSON
        payload_body = await request.body()
        # The secret should be stored securely, e.g., in Vault
        secret_credential = await vault_client.get_credential("github-webhook-secret")
        secret_token = secret_credential.secrets.get("token").encode('utf-8')

        h = hmac.new(secret_token, payload_body, hashlib.sha256)
        expected_signature = "sha256=" + h.hexdigest()

        if not hmac.compare_digest(expected_signature, x_hub_signature_256):
            raise HTTPException(status_code=403, detail="Invalid signature.")
    except Exception as e:
        logger.error(f"GitHub signature verification failed: {e}", exc_info=True)
        raise HTTPException(status_code=403, detail="Invalid signature.")


@router.post("/github", dependencies=[Depends(verify_github_signature)])
async def handle_github_webhook(request: Request):
    """
    This endpoint receives incoming webhooks from GitHub, verifies their
    signature, and triggers the appropriate flow.
    """
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    if event_type == "pull_request":
        action = payload.get("action")
        # Trigger the review flow when a PR is opened or a new commit is pushed
        if action in ["opened", "reopened", "synchronize"]:
            pr_info = payload.get("pull_request", {})
            repo_info = payload.get("repository", {})
            
            context = {
                "repo": repo_info.get("full_name"),
                "pr_number": pr_info.get("number"),
                "pr_title": pr_info.get("title"),
                "pr_body": pr_info.get("body"),
                "pr_url": pr_info.get("html_url"),
            }

            # Publish an event about the webhook
            await publish_event(
                event_type="webhook.github.pull_request",
                source="IntegrationHub",
                payload={
                    "github_event": event_type,
                    "action": action,
                    "context": context
                }
            )
            
            # Asynchronously trigger the code review flow
            await engine.run_flow_by_id("code_review_agent", data_context=context)
            
            return {"status": "Code review flow triggered successfully."}

    return {"status": "Webhook received, but no action taken."} 