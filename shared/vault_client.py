import hvac
import os
import logging

logger = logging.getLogger(__name__)

class VaultClient:
    """A simple client for interacting with HashiCorp Vault."""

    def __init__(self, vault_addr: str = None, vault_token: str = None):
        self.client = hvac.Client(
            url=vault_addr or os.environ.get('VAULT_ADDR'),
            token=vault_token or os.environ.get('VAULT_TOKEN')
        )
        if self.client.is_authenticated():
            logger.info("Vault client authenticated successfully.")
        else:
            raise ConnectionError("Failed to authenticate with Vault. Check VAULT_ADDR and VAULT_TOKEN.")

    def read_secret(self, path: str, key: str) -> str:
        """
        Reads a specific key from a secret at a given path.

        Args:
            path: The path to the secret in Vault (e.g., 'secret/data/openai').
            key: The key within the secret to retrieve.

        Returns:
            The secret value.
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(path=path)
            return response['data']['data'][key]
        except Exception as e:
            logger.error(f"Failed to read secret '{key}' from path '{path}': {e}", exc_info=True)
            raise 