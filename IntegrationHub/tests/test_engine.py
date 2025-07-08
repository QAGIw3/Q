import pytest
import zulip
import uuid

from IntegrationHub.app.models.flow import Flow, FlowStep, FlowTrigger
from IntegrationHub.app.core.engine import run_flow
from IntegrationHub.app.core import vault_client

@pytest.fixture
def mock_zulip_client(monkeypatch):
    """
    Mocks the zulip.Client to avoid real network calls and to assert
    that the Zulip API was called correctly.
    """
    def mock_init(self, *args, **kwargs):
        pass

    def mock_send_message(self, message):
        assert message["type"] == "stream"
        assert message["to"] == "test-stream"
        assert message["topic"] == "test-topic"
        assert "Hello from the test flow!" in message["content"]
        return {"result": "success", "id": 12345}

    monkeypatch.setattr(zulip.Client, "__init__", mock_init)
    monkeypatch.setattr(zulip.Client, "send_message", mock_send_message)

def test_run_flow_with_zulip_connector(mock_zulip_client, capsys):
    """
    Tests running a simple flow with the Zulip connector using credentials from the vault.
    """
    # 1. Store a secret in the mock vault
    cred_id = str(uuid.uuid4())
    secrets = {
        "email": "test-bot@example.com",
        "api_key": "test-key",
        "site": "https://example.zulipchat.com"
    }
    vault_client.store_secret(cred_id, secrets)

    # 2. Create a flow that references the credential
    flow = Flow(
        id="test-flow-1",
        name="Test Zulip Notification",
        trigger=FlowTrigger(type="manual", configuration={}),
        steps=[
            FlowStep(
                name="Send a test message",
                connector_id="zulip-message",
                credential_id=cred_id,
                configuration={
                    # Non-secret config goes here
                    "stream": "test-stream",
                    "topic": "test-topic",
                    "content": "Hello from the test flow!"
                }
            )
        ]
    )

    run_flow(flow, data_context={})

    captured = capsys.readouterr()
    assert "--- Running Flow: Test Zulip Notification ---" in captured.out
    assert "  - Executing step: Send a test message" in captured.out
    assert "    Step 'Send a test message' completed successfully." in captured.out
    assert "--- Flow Finished: Test Zulip Notification ---" in captured.out
    
    # Clean up the vault
    vault_client.delete_secret(cred_id)

def test_run_flow_with_failing_zulip_connector(monkeypatch, capsys):
    """
    Tests a flow where the Zulip API returns an error.
    """
    def mock_init(self, *args, **kwargs):
        pass

    def mock_send_message_failure(self, message):
        return {"result": "error", "msg": "Invalid API key"}

    monkeypatch.setattr(zulip.Client, "__init__", mock_init)
    monkeypatch.setattr(zulip.Client, "send_message", mock_send_message_failure)

    cred_id = str(uuid.uuid4())
    secrets = {"api_key": "invalid-key", "email": "test-bot@example.com", "site": "https://example.zulipchat.com"}
    vault_client.store_secret(cred_id, secrets)

    flow = Flow(
        id="test-flow-failing",
        name="Test Failing Zulip Flow",
        trigger=FlowTrigger(type="manual", configuration={}),
        steps=[
            FlowStep(
                name="This step will fail",
                connector_id="zulip-message",
                credential_id=cred_id,
                configuration={
                    "stream": "test-stream",
                    "topic": "test-topic",
                    "content": "This should not be sent"
                }
            )
        ]
    )

    run_flow(flow, data_context={})

    captured = capsys.readouterr()
    assert "--- Running Flow: Test Failing Zulip Flow ---" in captured.out
    assert "  - Executing step: This step will fail" in captured.out
    assert "    ERROR: Step 'This step will fail' failed" in captured.out
    assert "Failed to send message to Zulip: Invalid API key" in captured.out
    assert "--- Flow Finished: Test Failing Zulip Flow ---" in captured.out
    
    # Clean up the vault
    vault_client.delete_secret(cred_id) 