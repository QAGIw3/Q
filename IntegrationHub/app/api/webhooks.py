from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

from ..core.pulsar_client import publish_flow_trigger
from .flows import flows_db  # Import the in-memory db for now

router = APIRouter()

@router.post("/{hook_id}")
async def handle_webhook(hook_id: str, request: Request):
    """
    This endpoint receives incoming webhooks.
    It finds the corresponding flow and publishes a trigger message to Pulsar.
    """
    # Find the flow associated with this hook_id
    # In a real system, this would be an efficient DB lookup.
    # For this PoC, we iterate through the in-memory DB.
    target_flow = None
    for flow in flows_db.values():
        if flow.trigger.type == 'webhook' and flow.trigger.configuration.get('hook_id') == hook_id:
            target_flow = flow
            break
            
    if not target_flow:
        raise HTTPException(status_code=404, detail=f"Webhook with ID '{hook_id}' not found or not configured for any flow.")

    # Get the webhook payload
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw_body": await request.body().decode('utf-8')}

    # Publish the trigger message with the webhook payload
    publish_flow_trigger(target_flow, trigger_data=payload)

    return {"message": "Webhook received and flow triggered."} 