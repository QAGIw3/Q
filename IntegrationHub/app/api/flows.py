from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
from pydantic import BaseModel

from app.core.engine import engine
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

router = APIRouter()

# --- Pre-defined Flows ---
# In a real system, these would be stored in a database.
PREDEFINED_FLOWS: Dict[str, Dict[str, Any]] = {
    "send-summary-email": {
        "id": "send-summary-email",
        "name": "Send Summary Email via SMTP",
        "description": "A flow to send an email. Requires 'to', 'subject', and 'body' in the parameters.",
        "steps": [
            {
                "name": "Send Email",
                "connector_id": "smtp-email",
                "action_id": "send",
                # This credential must be created in Vault beforehand
                "credential_id": "smtp-credentials", 
                # The 'configuration' here is filled by the trigger parameters
            }
        ]
    },
    "ingest-zulip-to-kg": {
        "id": "ingest-zulip-to-kg",
        "name": "Ingest Zulip Stream to Knowledge Graph",
        "description": "Fetches recent messages from a Zulip stream and publishes them to a Pulsar topic for ingestion into the Knowledge Graph.",
        "steps": [
            {
                "name": "Fetch Messages from Zulip",
                "connector_id": "zulip",
                "action_id": "get-messages",
                "credential_id": "zulip-credentials",
                "configuration": {
                    "stream": "knowledge-graph",
                    "num_before": 50
                }
            },
            {
                "name": "Publish to Pulsar for KG Ingestion",
                "connector_id": "pulsar-publish",
                "action_id": "default_action", # Not strictly needed, but good for clarity
                "configuration": {
                    "topic": "persistent://public/default/knowledge-graph-ingestion",
                    # The 'message' will be the output from the previous step
                    # The engine now maps this automatically.
                }
            }
        ]
    }
}


class Flow(BaseModel):
    id: str
    name: str
    description: str

class TriggerRequest(BaseModel):
    parameters: Dict[str, Any]


@router.get("", response_model=List[Flow])
async def list_flows(user: UserClaims = Depends(get_current_user)):
    """Lists all available pre-defined flows."""
    return [Flow(**flow) for flow in PREDEFINED_FLOWS.values()]

@router.post("/{flow_id}/trigger")
async def trigger_flow(
    flow_id: str,
    request: TriggerRequest,
    user: UserClaims = Depends(get_current_user)
):
    """Triggers a pre-defined flow by its ID."""
    if flow_id not in PREDEFINED_FLOWS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found.")
    
    flow_config = PREDEFINED_FLOWS[flow_id]
    
    # The new engine handles parameter mapping internally.
    # The initial trigger parameters are passed as the starting data_context.
    await engine.run_flow(flow_config, data_context=request.parameters)
    
    return {"status": "Flow triggered successfully", "flow_id": flow_id} 