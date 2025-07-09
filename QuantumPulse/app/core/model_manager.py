# QuantumPulse/app/core/model_manager.py
import logging
import os
from threading import Lock
from typing import Dict, Any

from transformers import AutoModelForCausalLM, AutoTokenizer
from shared.vault_client import VaultClient

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Manages the lifecycle of ML models, including loading, unloading,
    and swapping, without service restarts.
    """
    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._tokenizers: Dict[str, Any] = {}
        self._lock = Lock()
        self._hf_token = None

    def _get_hf_token(self) -> str:
        """Retrieves the Hugging Face token from Vault, caching it."""
        if self._hf_token is None:
            try:
                vault_client = VaultClient()
                self._hf_token = vault_client.read_secret("secret/data/huggingface", "token")
                if not self._hf_token:
                    raise ValueError("Hugging Face token not found in Vault.")
            except Exception as e:
                logger.error(f"Failed to get Hugging Face token from Vault: {e}", exc_info=True)
                raise
        return self._hf_token

    def load_model(self, model_name: str):
        """
        Downloads a model from the Hugging Face Hub and loads it into memory.
        If the model is already loaded, this function does nothing.
        """
        with self._lock:
            if model_name in self._models:
                logger.info(f"Model '{model_name}' is already loaded.")
                return

            logger.info(f"Loading model '{model_name}' from the Hub...")
            try:
                token = self._get_hf_token()
                # In a real production system, you would specify a cache_dir
                # to a persistent volume to avoid re-downloading on pod restarts.
                model = AutoModelForCausalLM.from_pretrained(model_name, token=token)
                tokenizer = AutoTokenizer.from_pretrained(model_name, token=token)
                
                self._models[model_name] = model
                self._tokenizers[model_name] = tokenizer
                logger.info(f"Successfully loaded model '{model_name}'.")
            except Exception as e:
                logger.error(f"Failed to load model '{model_name}': {e}", exc_info=True)
                raise

    def get_model_and_tokenizer(self, model_name: str) -> (Any, Any):
        """
        Retrieves a loaded model and its tokenizer.
        """
        with self._lock:
            if model_name not in self._models:
                # Attempt to load it on-demand
                self.load_model(model_name)
            
            return self._models.get(model_name), self._tokenizers.get(model_name)

# Singleton instance
model_manager = ModelManager() 