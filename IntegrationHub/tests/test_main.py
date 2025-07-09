from fastapi.testclient import TestClient
from IntegrationHub.app.main import app

client = TestClient(app)

def test_health_check():
    """
    Tests that the /health endpoint returns a 200 OK response.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"} 