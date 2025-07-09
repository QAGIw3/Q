from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from pydantic import BaseModel

from app.core.engine import engine

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
                # This credential must be created in Vault beforehand
                "credential_id": "smtp-credentials", 
                # The 'configuration' here is filled by the trigger parameters
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
async def list_flows():
    """Lists all available pre-defined flows."""
    return [Flow(**flow) for flow in PREDEFINED_FLOWS.values()]

@router.post("/{flow_id}/trigger")
async def trigger_flow(flow_id: str, request: TriggerRequest):
    """Triggers a pre-defined flow by its ID."""
    if flow_id not in PREDEFINED_FLOWS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found.")
    
    flow_config = PREDEFINED_FLOWS[flow_id]
    
    # Simple parameter mapping: The trigger parameters become the step configuration
    # A more complex engine would have more sophisticated mapping logic.
    flow_config["steps"][0]["configuration"] = request.parameters
    
    # We run the flow asynchronously in the background
    await engine.run_flow(flow_config, data_context=request.parameters)
    
    return {"status": "Flow triggered successfully", "flow_id": flow_id} 