import logging
import emails
from emails.template import JinjaTemplate
from typing import Dict, Any, Optional

from app.models.connector import BaseConnector, ConnectorAction
from app.core.vault_client import vault_client

logger = logging.getLogger(__name__)

class EmailConnector(BaseConnector):
    """A connector for sending emails via SMTP."""

    @property
    def connector_id(self) -> str:
        return "smtp-email"

    async def execute(self, action: ConnectorAction, configuration: Dict[str, Any], data_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if action.action_id != "send":
            raise ValueError(f"Unsupported action for Email connector: {action.action_id}")

        # Get SMTP credentials from Vault
        smtp_credentials = await vault_client.get_credential(action.credential_id)
        
        # Merge credentials with other SMTP settings (like host/port)
        smtp_config = {**smtp_credentials.secrets, **configuration.get("smtp_server", {})}

        message = emails.Message(
            subject=JinjaTemplate(configuration["subject"]),
            html=JinjaTemplate(configuration["body"]),
            mail_from=("Q Platform", "noreply@q-platform.dev")
        )
        
        try:
            response = message.send(
                to=configuration["to"],
                smtp=smtp_config
            )
            logger.info(f"Successfully sent email to {configuration['to']} with subject '{configuration['subject']}'")
            return {"status": "sent", "response_code": response.status_code}
        except Exception as e:
            logger.error(f"Failed to send email to {configuration['to']}: {e}", exc_info=True)
            raise

# Instantiate a single instance
email_connector = EmailConnector() 