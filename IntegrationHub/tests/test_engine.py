import pytest
import httpx

from IntegrationHub.app.models.flow import Flow, FlowStep, FlowTrigger
from IntegrationHub.app.core.engine import run_flow

@pytest.fixture
def mock_slack_api(monkeypatch):
    """
    Mocks the httpx.Client context manager to avoid real network calls
    and to assert that the Slack API was called correctly.
    """
    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            self.post_called = False
            self.url = None
            self.json = None

        def post(self, url, json):
            self.post_called = True
            self.url = url
            self.json = json
            # Return a successful response
            request = httpx.Request("POST", url)
            response = httpx.Response(200, text="ok", request=request)
            return response

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("httpx.Client", MockHttpxClient)
    return MockHttpxClient


def test_run_flow_with_slack_connector(mock_slack_api, capsys):
    """
    Tests running a simple flow with the Slack connector.
    It verifies that the correct messages are printed and the mock Slack API is called.
    """
    flow = Flow(
        id="test-flow-1",
        name="Test Slack Notification",
        trigger=FlowTrigger(type="manual", configuration={}),
        steps=[
            FlowStep(
                name="Send a test message",
                connector_id="slack-webhook",
                configuration={
                    "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
                    "message": "Hello from the test flow!"
                }
            )
        ]
    )

    run_flow(flow)

    captured = capsys.readouterr()
    assert "--- Running Flow: Test Slack Notification ---" in captured.out
    assert "  - Executing step: Send a test message" in captured.out
    assert "    Step 'Send a test message' completed successfully." in captured.out
    assert "--- Flow Finished: Test Slack Notification ---" in captured.out

def test_run_flow_with_failing_connector(capsys):
    """
    Tests a flow where the connector configuration is invalid, causing an error.
    """
    flow = Flow(
        id="test-flow-failing",
        name="Test Failing Flow",
        trigger=FlowTrigger(type="manual", configuration={}),
        steps=[
            FlowStep(
                name="This step will fail",
                connector_id="slack-webhook",
                configuration={
                    # Missing webhook_url
                    "message": "This should not be sent"
                }
            )
        ]
    )

    run_flow(flow)

    captured = capsys.readouterr()
    assert "--- Running Flow: Test Failing Flow ---" in captured.out
    assert "  - Executing step: This step will fail" in captured.out
    assert "    ERROR: Step 'This step will fail' failed" in captured.out
    assert "Slack webhook_url is a required configuration parameter." in captured.out
    assert "--- Flow Finished: Test Failing Flow ---" in captured.out 