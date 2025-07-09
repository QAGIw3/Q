import hvac
import os
import logging

logger = logging.getLogger(__name__)

# The standard path where a service account token is mounted in a pod
K8S_SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
# The Vault role created by Terraform for our services
VAULT_K8S_ROLE = "q-platform-role"

class VaultClient:
    """A client for HashiCorp Vault that can use K8s auth."""

    def __init__(self, vault_addr: str = None):
        self._vault_addr = vault_addr or os.environ.get('VAULT_ADDR')
        self.client = hvac.Client(url=self._vault_addr)
        self._authenticate()

    def _authenticate(self):
        """
        Authenticates with Vault. Prefers K8s auth, falls back to token auth.
        """
        # Case 1: Running in Kubernetes
        if os.path.exists(K8S_SA_TOKEN_PATH):
            logger.info("Detected Kubernetes environment. Attempting K8s auth.")
            try:
                with open(K8S_SA_TOKEN_PATH, 'r') as f:
                    jwt = f.read()
                
                self.client.auth.kubernetes.login(
                    role=VAULT_K8S_ROLE,
                    jwt=jwt
                )
                if self.client.is_authenticated():
                    logger.info("Vault client authenticated successfully using Kubernetes service account.")
                    return
            except Exception as e:
                logger.error(f"Kubernetes auth failed: {e}. Falling back to token auth.", exc_info=True)

        # Case 2: Fallback to token (for local dev)
        token = os.environ.get('VAULT_TOKEN')
        if token:
            self.client.token = token
            if self.client.is_authenticated():
                logger.info("Vault client authenticated successfully using VAULT_TOKEN.")
                return

        raise ConnectionError("Failed to authenticate with Vault. No valid k8s token or VAULT_TOKEN found.")

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