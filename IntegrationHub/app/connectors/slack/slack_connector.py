import httpx
from typing import Dict, Any

class SlackSink:
    def __init__(self, config: Dict[str, Any]):
        self.webhook_url = config.get("webhook_url")
        self.message_template = config.get("message", "A flow step was triggered.")
        if not self.webhook_url:
            raise ValueError("Slack webhook_url is a required configuration parameter.")

    def write(self, data: Dict[str, Any]):
        """
        Sends a message to the configured Slack webhook.
        The 'data' parameter can be used to format the message in the future.
        """
        try:
            # For now, we send a static message. This can be templated later.
            payload = {"text": self.message_template}
            with httpx.Client() as client:
                response = client.post(self.webhook_url, json=payload)
                response.raise_for_status()  # Raise an exception for bad status codes
        except httpx.RequestError as e:
            # Handle connection errors, timeouts, etc.
            print(f"An error occurred while sending message to Slack: {e}")
            raise
        except httpx.HTTPStatusError as e:
            # Handle bad responses (4xx or 5xx)
            print(f"Received an error response from Slack: {e.response.status_code} - {e.response.text}")
            raise

def get_connector(*args, **kwargs):
    return SlackSink(*args, **kwargs)
