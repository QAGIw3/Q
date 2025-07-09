import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Patch the Milvus handler's connect method before importing the app
with patch('VectorStoreQ.app.core.milvus_handler.MilvusHandler.connect', return_value=None):
    from VectorStoreQ.app.main import app

client = TestClient(app)

def test_health_check():
    """
    Tests that the /health endpoint returns a 200 OK response.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

