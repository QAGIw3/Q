# H2M/app/services/model_registry.py
import logging
from typing import List, Optional

from app.services.ignite_client import ignite_client
from app.h2m_models import ModelRegistryEntry, ModelMetadata

logger = logging.getLogger(__name__)

MODEL_REGISTRY_CACHE_NAME = "model_registry"

class ModelRegistryService:
    def __init__(self):
        self._cache = None

    async def get_cache(self):
        """Initializes and returns the Ignite cache for the model registry."""
        if self._cache is None:
            await ignite_client.connect() # Ensure client is connected
            self._cache = ignite_client.get_or_create_cache(MODEL_REGISTRY_CACHE_NAME)
        return self._cache

    async def register_model(self, model_metadata: ModelMetadata) -> ModelRegistryEntry:
        """
        Registers a new model in the registry.

        Args:
            model_metadata: The metadata of the model to register.

        Returns:
            The created registry entry.
        """
        cache = await self.get_cache()
        entry = ModelRegistryEntry(metadata=model_metadata)
        
        # The model name is the key
        cache.put(model_metadata.model_name, entry.dict())
        logger.info(f"Successfully registered model '{model_metadata.model_name}'.")
        return entry

    async def get_model(self, model_name: str) -> Optional[ModelRegistryEntry]:
        """
        Retrieves a model entry from the registry by its name.
        """
        cache = await self.get_cache()
        entry_dict = cache.get(model_name)
        if entry_dict:
            return ModelRegistryEntry(**entry_dict)
        return None

    async def list_models(self) -> List[ModelRegistryEntry]:
        """
        Lists all models currently in the registry.
        """
        cache = await self.get_cache()
        models = []
        for _, entry_dict in cache.scan():
            models.append(ModelRegistryEntry(**entry_dict))
        return models
    
    async def set_active_model(self, model_name: str) -> bool:
        """
        Sets a model as active for a given base model type.
        This deactivates other models of the same base model.
        """
        entry = await self.get_model(model_name)
        if not entry:
            logger.warning(f"Cannot activate model '{model_name}': not found in registry.")
            return False
        
        # Deactivate other models with the same base model
        all_models = await self.list_models()
        for model in all_models:
            if model.metadata.base_model == entry.metadata.base_model and model.is_active:
                model.is_active = False
                await self.get_cache().put(model.metadata.model_name, model.dict())

        # Activate the target model
        entry.is_active = True
        await self.get_cache().put(model_name, entry.dict())
        logger.info(f"Successfully activated model '{model_name}'.")
        return True

# Singleton instance
model_registry_service = ModelRegistryService() 