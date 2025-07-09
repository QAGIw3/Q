import logging
import httpx
import asyncio
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool
from shared.vault_client import VaultClient

logger = logging.getLogger(__name__)

# --- Airflow Configuration ---
# In a real system, these would be managed more robustly.
# We will fetch them from Vault.
AIRFLOW_CONFIG_VAULT_PATH = "secret/data/airflow"

def _get_airflow_config(config: Dict[str, Any]) -> (str, httpx.AsyncClient):
    """
    Helper function to get Airflow config from Vault and return a client.
    """
    try:
        airflow_url = config.get("airflow_url")
        if not airflow_url:
            raise ValueError("airflow_url not found in tool configuration.")

        vault_client = config.get("vault_client")
        if not vault_client or not isinstance(vault_client, VaultClient):
            raise ValueError("VaultClient not found or invalid in tool configuration.")

        username = vault_client.read_secret(AIRFLOW_CONFIG_VAULT_PATH, "username")
        password = vault_client.read_secret(AIRFLOW_CONFIG_VAULT_PATH, "password")

        if not all([username, password]):
            raise ValueError("Airflow username or password not found in Vault.")

        client = httpx.AsyncClient(
            base_url=airflow_url,
            auth=(username, password),
            timeout=60.0
        )
        return airflow_url, client
    except Exception as e:
        logger.error(f"Failed to get Airflow configuration from Vault: {e}", exc_info=True)
        raise ConnectionError("Could not configure Airflow client from Vault.")


async def trigger_dag_async(dag_id: str, conf: Dict[str, Any] = None, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Asynchronously triggers a DAG run in Airflow.
    """
    airflow_url, client = _get_airflow_config(config)
    endpoint = f"/api/v1/dags/{dag_id}/dagRuns"
    payload = {"conf": conf or {}}

    try:
        async with client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully triggered DAG '{dag_id}'.")
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Error triggering DAG '{dag_id}': {e.response.status_code} - {e.response.text}")
        raise
    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting {e.request.url!r}.")
        raise

def trigger_dag(dag_id: str, conf: Dict[str, Any] = None, config: Dict[str, Any] = None) -> str:
    """
    Triggers a DAG run in Airflow. This is a synchronous wrapper.
    """
    try:
        result = asyncio.run(trigger_dag_async(dag_id, conf, config))
        dag_run_id = result.get('dag_run_id')
        return f"Successfully triggered DAG '{dag_id}'. The DAG Run ID is: {dag_run_id}"
    except Exception as e:
        return f"Error triggering DAG '{dag_id}': {e}"


async def get_dag_run_status_async(dag_id: str, dag_run_id: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Asynchronously gets the status of a specific DAG run.
    """
    airflow_url, client = _get_airflow_config(config)
    endpoint = f"/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}"

    try:
        async with client:
            response = await client.get(endpoint)
            response.raise_for_status()
            logger.info(f"Successfully fetched status for DAG run '{dag_run_id}'.")
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Error fetching DAG run status: {e.response.status_code} - {e.response.text}")
        raise

def get_dag_run_status(dag_id: str, dag_run_id: str, config: Dict[str, Any] = None) -> str:
    """
    Gets the status of a specific DAG run. This is a synchronous wrapper.
    """
    try:
        result = asyncio.run(get_dag_run_status_async(dag_id, dag_run_id, config))
        return f"Status for DAG '{dag_id}', Run '{dag_run_id}': {result.get('state')}. Full details: {result}"
    except Exception as e:
        return f"Error fetching status for DAG run '{dag_run_id}': {e}"


# --- Tool Registration ---

trigger_dag_tool = Tool(
    name="trigger_airflow_dag",
    description="Triggers a specified Airflow DAG (Directed Acyclic Graph) to run. Use this to initiate complex, scheduled, or long-running data processing workflows.",
    func=trigger_dag
)

get_dag_status_tool = Tool(
    name="get_airflow_dag_status",
    description="Checks the status of a previously triggered Airflow DAG run using its DAG ID and DAG Run ID.",
    func=get_dag_run_status
) 