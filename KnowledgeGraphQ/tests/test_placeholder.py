import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# We need to patch the gremlin_client's connect method before importing the app
with patch('managerQ.app.core.gremlin_client.GremlinClient.connect', return_value=None):
    from KnowledgeGraphQ.app.main import app

client = TestClient(app)

def test_health_check():
    """
    Tests that the /health endpoint returns a 200 OK response.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

