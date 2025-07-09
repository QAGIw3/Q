import logging
import asyncio
from typing import Dict, Any, Optional

from app.models.connector import Connector, ConnectorAction
from app.connectors.zulip.zulip_connector import zulip_connector
from app.connectors.smtp.email_connector import email_connector
from app.connectors.pulsar.pulsar_connector import pulsar_publisher_connector
from app.core.vault_client import vault_client

# A registry of all available connector instances
AVAILABLE_CONNECTORS: Dict[str, Connector] = {
    zulip_connector.connector_id: zulip_connector,
    email_connector.connector_id: email_connector,
    pulsar_publisher_connector.connector_id: pulsar_publisher_connector,
}

class FlowExecutionEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def _execute_step(self, step_config: Dict[str, Any], data_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        connector_id = step_config.get("connector_id")
        credential_id = step_config.get("credential_id")
        action_id = step_config.get("action_id", "default_action") # Default action if not specified
        step_params = step_config.get("configuration", {})

        if connector_id not in AVAILABLE_CONNECTORS:
            raise ValueError(f"Connector '{connector_id}' not found.")

        connector = AVAILABLE_CONNECTORS[connector_id]
        
        # Prepare action for the connector
        action = ConnectorAction(
            action_id=action_id,
            credential_id=credential_id,
            configuration=step_params
        )

        # Pass the context from the previous step to the current step
        # A more advanced engine would have better data mapping (e.g., using JMESPath)
        merged_params = {**step_params, **data_context}
        action.configuration = merged_params
        
        self.logger.info(f"Executing action '{action.action_id}' on connector '{connector.connector_id}'")

        # Execute and return the result, which will become the context for the next step
        result = await connector.execute(action, configuration=action.configuration, data_context=data_context)
        return result

    async def run_flow(self, flow: Dict[str, Any], data_context: Dict[str, Any]):
        self.logger.info(f"--- Running Flow: {flow.get('name')} ---")
        
        current_context = data_context
        self.logger.info(f"    Initial data context: {current_context}")

        for step in flow.get("steps", []):
            self.logger.info(f"  - Executing step: {step.get('name')}")
            try:
                # The output of a step becomes the input context for the next
                step_result = await self._execute_step(step, current_context)
                
                if step_result:
                    current_context = {**current_context, **step_result} # Merge results into context

                self.logger.info(f"    Step '{step.get('name')}' completed. New context keys: {list(step_result.keys()) if step_result else []}")

            except Exception as e:
                self.logger.error(f"    ERROR: Step '{step.get('name')}' failed: {e}", exc_info=True)
                # In a real engine, we'd have error handling, retries, etc.
                break # Stop flow on first failure
        self.logger.info(f"--- Flow Finished: {flow.get('name')} ---")


engine = FlowExecutionEngine() 