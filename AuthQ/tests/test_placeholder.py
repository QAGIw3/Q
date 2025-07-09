from fastapi.testclient import TestClient
from unittest.mock import patch

# We must patch KeycloakOpenID to avoid it trying to connect during tests
with patch('AuthQ.app.main.KeycloakOpenID', return_value=None):
    from AuthQ.app.main import app

client = TestClient(app)

def test_health_check():
    """
    Tests that the /health endpoint returns a 200 OK response.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

