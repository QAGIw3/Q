import zulip
import logging
from typing import Dict, Any, Optional

from app.models.connector import BaseConnector, ConnectorAction
from app.core.vault_client import vault_client

logger = logging.getLogger(__name__)

class ZulipConnector(BaseConnector):
    """
    A connector for interacting with the Zulip API.
    Supports sending messages and fetching recent messages.
    """

    @property
    def connector_id(self) -> str:
        return "zulip"

    async def _get_client(self, credential_id: str) -> zulip.Client:
        """Helper to get an authenticated Zulip client."""
        credentials = await vault_client.get_credential(credential_id)
        return zulip.Client(
            email=credentials.secrets.get("email"),
            api_key=credentials.secrets.get("api_key"),
            site=credentials.secrets.get("site")
        )

    async def execute(self, action: ConnectorAction, configuration: Dict[str, Any], data_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = await self._get_client(action.credential_id)

        if action.action_id == "send-message":
            return await self._send_message(client, configuration)
        elif action.action_id == "get-messages":
            return await self._get_messages(client, configuration)
        else:
            raise ValueError(f"Unsupported action for Zulip connector: {action.action_id}")

    async def _send_message(self, client: zulip.Client, config: Dict[str, Any]) -> None:
        """Sends a message to a Zulip stream."""
        request = {
            "type": "stream",
            "to": config.get("stream"),
            "topic": config.get("topic"),
            "content": config.get("content", "A flow step was triggered."),
        }
        result = client.send_message(request)
        if result.get("result") != "success":
            raise RuntimeError(f"Failed to send message to Zulip: {result.get('msg')}")
        logger.info("Successfully sent message to Zulip.")
        return None

    async def _get_messages(self, client: zulip.Client, config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches recent messages from a Zulip stream."""
        num_before = config.get("num_before", 20)
        num_after = config.get("num_after", 0)
        
        request = {
            "anchor": "newest",
            "num_before": num_before,
            "num_after": num_after,
            "narrow": [
                {"operator": "stream", "operand": config.get("stream")}
            ]
        }
        if config.get("topic"):
            request["narrow"].append({"operator": "topic", "operand": config.get("topic")})
            
        result = client.get_messages(request)

        if result.get("result") != "success":
            raise RuntimeError(f"Failed to get messages from Zulip: {result.get('msg')}")

        logger.info(f"Successfully fetched {len(result['messages'])} messages from Zulip.")
        # Return the messages so they can be used in the next step
        return {"messages": result["messages"]}

# Instantiate a single instance of the connector for the engine to use
zulip_connector = ZulipConnector()
