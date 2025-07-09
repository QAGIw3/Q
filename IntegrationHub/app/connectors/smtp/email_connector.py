import logging
import emails
from emails.template import JinjaTemplate
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EmailConnector:
    """A connector for sending emails via SMTP."""

    def __init__(self, smtp_config: Dict[str, Any]):
        """
        Initializes the connector with SMTP server details.
        
        Args:
            smtp_config: A dict with keys like 'host', 'port', 'user', 'password', 'tls'.
        """
        self.smtp_config = smtp_config
        logger.info(f"EmailConnector initialized for host {smtp_config.get('host')}")

    def send(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Sends an email.
        
        Args:
            to: The recipient's email address.
            subject: The email subject.
            body: The email body (can be HTML).
            
        Returns:
            The response from the SMTP server.
        """
        message = emails.Message(
            subject=JinjaTemplate(subject),
            html=JinjaTemplate(body),
            mail_from=("Q Platform", "noreply@q-platform.dev")
        )
        
        try:
            response = message.send(
                to=to,
                smtp=self.smtp_config
            )
            logger.info(f"Successfully sent email to {to} with subject '{subject}'")
            return {"status_code": response.status_code, "response": str(response.response)}
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}", exc_info=True)
            raise 