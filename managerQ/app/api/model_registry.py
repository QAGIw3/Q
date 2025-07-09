# managerQ/app/api/model_registry.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from shared.q_h2m_client.client import H2MClient
import httpx

router = APIRouter()

# In a real app, this client would be managed via lifespan events.
# For simplicity, we create it here.
h2m_client = H2MClient(base_url="http://h2m-service:80")

@router.get("/models", response_model=List[Dict[str, Any]])
async def list_models_in_registry():
    """
    Lists all models available in the H2M model registry.
    """
    return await h2m_client.list_models()

@router.post("/models/{model_name}/activate")
async def activate_model_in_registry(model_name: str):
    """
    Activates a specific model in the H2M registry, making it available for inference.
    """
    try:
        result = await h2m_client.activate_model(model_name)
        return result
    except Exception as e:
        # The client will raise an exception on failure, which we can catch.
        # It might be better to let the client's exceptions propagate
        # or handle specific ones.
        raise HTTPException(status_code=500, detail=f"Failed to activate model: {e}") 