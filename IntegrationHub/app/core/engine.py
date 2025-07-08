import importlib
from typing import Dict, Any

from ..models.flow import Flow

def get_connector_instance(connector_id: str, config: Dict[str, Any]):
    """
    Dynamically imports and instantiates a connector.
    For now, it assumes a convention for module location.
    e.g., connector_id 'slack-webhook' maps to 'app.connectors.slack.slack_connector'
    """
    # This is a simplified mapping for the PoC
    connector_map = {
        "slack-webhook": "IntegrationHub.app.connectors.slack.slack_connector"
    }

    if connector_id not in connector_map:
        raise ValueError(f"Connector '{connector_id}' not found.")

    module_path = connector_map[connector_id]
    try:
        connector_module = importlib.import_module(module_path)
        connector_factory = getattr(connector_module, "get_connector")
        return connector_factory(config)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(f"Could not load connector '{connector_id}': {e}")


def run_flow(flow: Flow):
    """
    A very basic flow runner for the PoC.
    It iterates through the steps and executes the configured connector.
    """
    print(f"--- Running Flow: {flow.name} ---")
    for step in flow.steps:
        print(f"  - Executing step: {step.name}")
        try:
            connector = get_connector_instance(step.connector_id, step.configuration)
            # In a real engine, we would pass data between steps.
            # For this PoC, we pass an empty dict.
            connector.write(data={})
            print(f"    Step '{step.name}' completed successfully.")
        except (ValueError, RuntimeError, Exception) as e:
            print(f"    ERROR: Step '{step.name}' failed: {e}")
            # In a real engine, we'd have error handling, retries, etc.
            break # Stop flow on first failure for this PoC
    print(f"--- Flow Finished: {flow.name} ---") 