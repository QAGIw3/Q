import logging
import asyncio
import json
import re
from typing import Dict, Any, Optional

from app.models.connector import Connector, ConnectorAction
from app.connectors.zulip.zulip_connector import zulip_connector
from app.connectors.smtp.email_connector import email_connector
from app.connectors.pulsar.pulsar_connector import pulsar_publisher_connector
from app.connectors.http.http_connector import http_connector
from app.core.vault_client import vault_client

# A registry of all available connector instances
AVAILABLE_CONNECTORS: Dict[str, Connector] = {
    zulip_connector.connector_id: zulip_connector,
    email_connector.connector_id: email_connector,
    pulsar_publisher_connector.connector_id: pulsar_publisher_connector,
    http_connector.connector_id: http_connector,
}

class FlowExecutionEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _render_configuration(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Renders placeholders in a configuration dict using values from the context."""
        # Convert config to JSON string to find all placeholders
        config_str = json.dumps(config)
        
        # Find all placeholders like {{ key }} or {{ nested.key }}
        placeholders = re.findall(r"\{\{\s*([\w\.]+)\s*\}\}", config_str)
        
        for placeholder in placeholders:
            # Resolve the placeholder value from the context
            value = context
            try:
                for key in placeholder.split('.'):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break
            except (KeyError, TypeError):
                value = None

            # Replace the placeholder. Be careful to handle different types correctly.
            # This simplified approach converts all replacements to strings within the JSON structure.
            # A more robust solution might handle types more granularly.
            if value is not None:
                config_str = config_str.replace(f"{{{{ {placeholder} }}}}", json.dumps(value).strip('"'))

        return json.loads(config_str)

    async def _execute_step(self, step_config: Dict[str, Any], data_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        connector_id = step_config.get("connector_id")
        credential_id = step_config.get("credential_id")
        action_id = step_config.get("action_id", "default_action") # Default action if not specified
        
        # Render the step's configuration using the current flow context
        rendered_params = self._render_configuration(step_config.get("configuration", {}), data_context)

        if connector_id not in AVAILABLE_CONNECTORS:
            raise ValueError(f"Connector '{connector_id}' not found.")

        connector = AVAILABLE_CONNECTORS[connector_id]
        
        # Prepare action for the connector
        action = ConnectorAction(
            action_id=action_id,
            credential_id=credential_id,
            configuration=rendered_params
        )
        
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