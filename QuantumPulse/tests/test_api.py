import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# It's important to set up the app object before other imports
from app.main import app
from app.core.pulsar_client import PulsarManager, get_pulsar_manager

# Create a mock PulsarManager
mock_pulsar_manager = MagicMock(spec=PulsarManager)

def get_mock_pulsar_manager():
    """Dependency override for the PulsarManager."""
    return mock_pulsar_manager

# Override the dependency for the entire application
app.dependency_overrides[get_pulsar_manager] = get_mock_pulsar_manager

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    mock_pulsar_manager.reset_mock()

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_inference_request_success():
    """Test successful creation of an inference request."""
    # The endpoint now uses background tasks, so the mock call is on the task
    # We can use a trick to inspect the background task
    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        test_payload = {
            "prompt": "Hello, world!",
            "model": "test-model"
        }
        response = client.post("/api/v1/inference", json=test_payload)

        assert response.status_code == 202
        json_response = response.json()
        assert "message" in json_response
        assert "request_id" in json_response

        # Check if the background task was added correctly
        mock_add_task.assert_called_once()
        # Get the arguments passed to the background task
        args, kwargs = mock_add_task.call_args
        # The first argument is the callable (publish_request)
        # The keyword arguments contain the topic and request object
        assert kwargs['topic'] is not None
        assert kwargs['request'].prompt == "Hello, world!"
        assert kwargs['request'].model == "test-model"

def test_create_inference_request_validation_error():
    """Test for a validation error when the prompt is missing."""
    response = client.post("/api/v1/inference", json={"model": "test-model"})
    assert response.status_code == 422 # Unprocessable Entity

def test_pulsar_connection_error_handling():
    """Test how the API handles a Pulsar connection error."""
    # Configure the mock to raise an error
    mock_pulsar_manager.publish_request.side_effect = ConnectionError("Test connection failed")

    with patch("fastapi.BackgroundTasks.add_task", side_effect=mock_pulsar_manager.publish_request) as mock_add_task:
        test_payload = {"prompt": "This should fail"}
        
        # We need to simulate the background task execution to see the exception
        # This is a bit tricky. A simpler way is to test the publish_request function directly.
        # However, for an endpoint test, let's assume the error propagates.
        # Since the actual call is in a background task, the endpoint won't fail immediately.
        # The test as written before wouldn't work as expected.
        # A more direct test:
        from app.api.endpoints.inference import create_inference_request, REQUEST_TOPIC
        import asyncio

        async def run_test():
            background_tasks = MagicMock()
            background_tasks.add_task.side_effect = mock_pulsar_manager.publish_request
            from app.models.inference import InferenceRequest
            
            with pytest.raises(HTTPException) as excinfo:
                # This direct call won't work due to how Depends works outside of a request.
                # Let's stick to testing the endpoint's robustness in a different way.
                # The original test assumed the exception would be caught by FastAPI's handler,
                # but for background tasks, it's not that simple.
                # The endpoint itself should not fail. The failure happens in the background.
                pass

    # Let's re-verify the intended behavior: the endpoint returns 202, and the error happens in the background.
    # The user is not notified of this specific failure via the HTTP response.
    # Therefore, a 503 test is not accurate for background tasks.
    # The previous test was flawed. The correct test is that the API still returns 202.
    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        # This time, the added task itself will raise the error when executed.
        mock_add_task.side_effect = ConnectionError("Test connection failed")
        
        test_payload = {"prompt": "This will fail in the background"}
        
        # The endpoint should still succeed because the error is in the background.
        response = client.post("/api/v1/inference", json=test_payload)
        assert response.status_code == 202
        mock_add_task.assert_called_once() 