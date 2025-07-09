# tests/integration/test_auth_flow.py
import pytest
import subprocess
import os
import httpx
from tenacity import retry, stop_after_delay, wait_fixed

# Service URLs based on the docker-compose file
AUTHQ_URL = "http://localhost:8003"
MANAGERQ_URL = "http://localhost:8004"

@pytest.fixture(scope="session")
def services():
    """
    A session-scoped fixture that starts and stops the docker-compose services.
    """
    compose_file = os.path.join(os.path.dirname(__file__), "docker-compose.integration.yml")
    try:
        print("Building and starting services...")
        subprocess.run(["docker-compose", "-f", compose_file, "up", "--build", "-d"], check=True)
        
        # Wait for services to be healthy
        wait_for_service(AUTHQ_URL + "/health")
        wait_for_service(MANAGERQ_URL + "/health")
        
        print("Services are up and running.")
        yield
    finally:
        print("Stopping services...")
        subprocess.run(["docker-compose", "-f", compose_file, "down"], check=True)

@retry(stop=stop_after_delay(60), wait=wait_fixed(2))
def wait_for_service(url):
    """Waits for a service to become available by polling its health check endpoint."""
    try:
        with httpx.Client() as client:
            response = client.get(url)
            response.raise_for_status()
        print(f"Service at {url} is healthy.")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        print(f"Service at {url} not ready yet, retrying... ({e})")
        raise

def test_user_registration_and_search(services):
    """
    An end-to-end test that registers a user, logs in, and performs a search.
    This test currently will not pass because AuthQ relies on a live Keycloak instance,
    and managerQ on other services. This test structure is the goal.
    """
    # This test is expected to fail until we have a full test environment
    # with a test-instance of Keycloak and other dependencies.
    # I am marking it as xfail for now.
    pytest.xfail("This test requires a full environment with Keycloak and other services.")

    with httpx.Client() as client:
        # 1. Register a new user (This would fail without a live Keycloak)
        reg_response = client.post(f"{AUTHQ_URL}/api/v1/users/register", json={
            "username": "integration_test_user",
            "email": "test@example.com",
            "password": "password"
        })
        assert reg_response.status_code == 201

        # 2. Log in to get a token (This would also fail)
        token_response = client.post(f"{AUTHQ_URL}/api/v1/auth/token", json={
            "username": "integration_test_user",
            "password": "password"
        })
        assert token_response.status_code == 200
        access_token = token_response.json()["access_token"]
        
        # 3. Use the token to access a protected route on another service
        headers = {"Authorization": f"Bearer {access_token}"}
        search_response = client.post(f"{MANAGERQ_URL}/v1/search/", headers=headers, json={
            "query": "test query"
        })
        assert search_response.status_code == 200
        assert "ai_summary" in search_response.json() 