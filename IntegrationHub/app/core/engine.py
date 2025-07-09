import logging
import asyncio
from typing import Dict, Any

from app.connectors.zulip.zulip_connector import ZulipConnector
from app.connectors.smtp.email_connector import EmailConnector
from app.core.vault_client import vault_client

# In a real system, this would be more dynamic (e.g., using entrypoints)
AVAILABLE_CONNECTORS = {
    "zulip-message": ZulipConnector,
    "smtp-email": EmailConnector,
}

class FlowExecutionEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    async def _execute_step(self, step_config: Dict[str, Any]):
        connector_id = step_config.get("connector_id")
        credential_id = step_config.get("credential_id")
        step_params = step_config.get("configuration", {})

        if connector_id not in AVAILABLE_CONNECTORS:
            raise ValueError(f"Connector '{connector_id}' not found.")

        # Get credentials from Vault
        credentials = await vault_client.get_credential(credential_id)
        
        # Initialize the connector with credentials
        ConnectorClass = AVAILABLE_CONNECTORS[connector_id]
        # The credential 'secrets' dict should match the connector's expected config
        connector = ConnectorClass(credentials.secrets)
        
        # Here we assume a 'send' method. A more robust implementation
        # would have a BaseConnector with abstract methods.
        connector.send(**step_params)
        
        self.logger.info(f"Successfully executed step: {step_config.get('name')}")

    async def run_flow(self, flow: Dict[str, Any], data_context: Dict[str, Any]):
        self.logger.info(f"--- Running Flow: {flow.get('name')} ---")
        self.logger.info(f"    Initial data context: {data_context}")
        for step in flow.get("steps", []):
            self.logger.info(f"  - Executing step: {step.get('name')}")
            try:
                await self._execute_step(step)
            except (ValueError, RuntimeError, Exception) as e:
                self.logger.error(f"    ERROR: Step '{step.get('name')}' failed: {e}")
                # In a real engine, we'd have error handling, retries, etc.
                break # Stop flow on first failure for this PoC
        self.logger.info(f"--- Flow Finished: {flow.get('name')} ---") 