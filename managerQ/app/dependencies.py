# managerQ/app/dependencies.py
import os
from functools import lru_cache
from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_knowledgegraph_client.client import KnowledgeGraphClient
from shared.q_pulse_client.client import QuantumPulseClient

# In a real app, config would come from a more robust source
@lru_cache()
def get_vector_store_client() -> VectorStoreClient:
    return VectorStoreClient(base_url=os.getenv("VECTORSTORE_Q_URL", "http://vectorstoreq:8000"))

@lru_cache()
def get_kg_client() -> KnowledgeGraphClient:
    return KnowledgeGraphClient(base_url=os.getenv("KNOWLEDGEGRAPH_Q_URL", "http://knowledgegraphq:8000"))

@lru_cache()
def get_pulse_client() -> QuantumPulseClient:
    return QuantumPulseClient(base_url=os.getenv("QUANTUMPULSE_URL", "http://quantumpulse:8000")) 