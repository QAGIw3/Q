import importlib
from typing import Dict, Any

from ..models.flow import Flow, FlowStep
from ..core import vault_client

def get_connector_instance(step: FlowStep):
    """
    Dynamically imports and instantiates a connector, first enriching
    its configuration with secrets from the vault.
    """
    config = step.configuration.copy()
    
    # If a credential is provided, fetch it and merge it into the config
    if step.credential_id:
        secrets = vault_client.retrieve_secret(step.credential_id)
        if not secrets:
            raise ValueError(f"Secrets for credential_id '{step.credential_id}' not found in vault.")
        config.update(secrets)

    # This is a simplified mapping for the PoC
    connector_map = {
        "zulip-message": "IntegrationHub.app.connectors.zulip.zulip_connector"
    }

    connector_id = step.connector_id
    if connector_id not in connector_map:
        raise ValueError(f"Connector '{connector_id}' not found.")

    module_path = connector_map[connector_id]
    try:
        connector_module = importlib.import_module(module_path)
        connector_factory = getattr(connector_module, "get_connector")
        return connector_factory(config)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(f"Could not load connector '{connector_id}': {e}")


def run_flow(flow: Flow, data_context: Dict[str, Any]):
    """
    A very basic flow runner for the PoC.
    It iterates through the steps and executes the configured connector.
    """
    print(f"--- Running Flow: {flow.name} ---")
    print(f"    Initial data context: {data_context}")
    for step in flow.steps:
        print(f"  - Executing step: {step.name}")
        try:
            connector = get_connector_instance(step)
            # Pass the current data context to the connector
            connector.write(data=data_context)
            print(f"    Step '{step.name}' completed successfully.")
        except (ValueError, RuntimeError, Exception) as e:
            print(f"    ERROR: Step '{step.name}' failed: {e}")
            # In a real engine, we'd have error handling, retries, etc.
            break # Stop flow on first failure for this PoC
    print(f"--- Flow Finished: {flow.name} ---") 