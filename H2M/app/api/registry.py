# H2M/app/api/registry.py
from fastapi import APIRouter, HTTPException, status
from typing import List

from app.services.model_registry import model_registry_service
from app.h2m_models import ModelMetadata, ModelRegistryEntry

router = APIRouter()

@router.post("/register", response_model=ModelRegistryEntry, status_code=status.HTTP_201_CREATED)
async def register_model(model_metadata: ModelMetadata):
    """
    Endpoint to register a new fine-tuned model.
    This is typically called by an automated process like a Spark job.
    """
    try:
        entry = await model_registry_service.register_model(model_metadata)
        return entry
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ModelRegistryEntry])
async def list_models():
    """Lists all models in the registry."""
    return await model_registry_service.list_models()

@router.post("/{model_name}/activate", status_code=status.HTTP_200_OK)
async def activate_model(model_name: str):
    """Sets a specific model version as active for its base model type."""
    success = await model_registry_service.set_active_model(model_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found.")
    return {"message": f"Model '{model_name}' activated."} 