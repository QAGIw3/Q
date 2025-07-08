from fastapi import APIRouter, HTTPException, status
from typing import List, Dict

from ..models.flow import Flow
from ..core.engine import run_flow

router = APIRouter()

# In-memory database for demonstration purposes
flows_db: Dict[str, Flow] = {}

@router.post("/", response_model=Flow, status_code=status.HTTP_201_CREATED)
def create_flow(flow: Flow):
    """
    Create a new integration flow.
    """
    if flow.id in flows_db:
        raise HTTPException(status_code=400, detail=f"Flow with ID {flow.id} already exists")
    flows_db[flow.id] = flow
    return flow

@router.get("/", response_model=List[Flow])
def list_flows():
    """
    List all integration flows.
    """
    return list(flows_db.values())

@router.get("/{flow_id}", response_model=Flow)
def get_flow(flow_id: str):
    """
    Retrieve a single integration flow by its ID.
    """
    if flow_id not in flows_db:
        raise HTTPException(status_code=404, detail=f"Flow with ID {flow_id} not found")
    return flows_db[flow_id]

@router.put("/{flow_id}", response_model=Flow)
def update_flow(flow_id: str, flow: Flow):
    """
    Update an existing integration flow.
    """
    if flow_id not in flows_db:
        raise HTTPException(status_code=404, detail=f"Flow with ID {flow_id} not found")
    flows_db[flow_id] = flow
    return flow

@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flow(flow_id: str):
    """
    Delete an integration flow.
    """
    if flow_id not in flows_db:
        raise HTTPException(status_code=404, detail=f"Flow with ID {flow_id} not found")
    del flows_db[flow_id]
    return

@router.post("/{flow_id}/trigger", status_code=status.HTTP_202_ACCEPTED)
def trigger_flow(flow_id: str):
    """
    Manually trigger an integration flow to run.
    """
    if flow_id not in flows_db:
        raise HTTPException(status_code=404, detail=f"Flow with ID {flow_id} not found")
    
    flow = flows_db[flow_id]
    run_flow(flow) # Execute the flow using our simple engine

    return {"message": "Flow execution triggered successfully"} 