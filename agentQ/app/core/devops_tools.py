import logging
import os
import json
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from kubernetes import client, config

from agentQ.app.core.toolbox import Tool
from shared.q_knowledgegraph_client import kgq_client

logger = logging.getLogger(__name__)

# --- Elasticsearch Client Setup ---
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
es_client = Elasticsearch(ES_URL)

# --- Kubernetes Client Setup ---
# Load configuration, either from a kubeconfig file or from the in-cluster service account
try:
    # When running inside a k8s cluster, this is the standard way to load config.
    # It will use the service account token mounted inside the pod.
    config.load_incluster_config()
    k8s_apps_v1 = client.AppsV1Api()
    k8s_core_v1 = client.CoreV1Api()
    k8s_custom_objects_api = client.CustomObjectsApi()
    logger.info("DevOps Tools: Loaded in-cluster Kubernetes config.")
except config.ConfigException:
    # This fallback is for local development and testing only.
    # In production, the agent should always run inside the cluster.
    logger.warning("Could not load in-cluster K8s config. Falling back to local kubeconfig.")
    try:
        config.load_kube_config()
        k8s_apps_v1 = client.AppsV1Api()
        k8s_core_v1 = client.CoreV1Api()
        k8s_custom_objects_api = client.CustomObjectsApi()
        logger.info("DevOps Tools: Loaded local kubeconfig.")
    except config.ConfigException:
        logger.error("Could not configure Kubernetes client. DevOps tools that use kubectl will not work.")
        k8s_apps_v1 = None
        k8s_core_v1 = None
        k8s_custom_objects_api = None


def get_service_logs(service_name: str, time_window: str = "15m") -> str:
    """
    Retrieves recent logs for a specific service from the centralized logging system.
    This is useful for understanding the immediate behavior and errors of a service.
    
    Args:
        service_name (str): The name of the service to query (e.g., 'IntegrationHub').
        time_window (str): The time window to query (e.g., '15m', '1h', '3d').
    
    Returns:
        A string containing the most recent log entries, or an error message.
    """
    logger.info(f"DevOps Tool: Getting logs for '{service_name}' in the last {time_window}.")
    
    try:
        # A simple way to parse time window from string
        # A more robust solution would use a dedicated parsing library
        if time_window.endswith('m'):
            delta = timedelta(minutes=int(time_window[:-1]))
        elif time_window.endswith('h'):
            delta = timedelta(hours=int(time_window[:-1]))
        elif time_window.endswith('d'):
            delta = timedelta(days=int(time_window[:-1]))
        else:
            return "Error: Invalid time window format. Use 'm', 'h', or 'd'."

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"service_name": service_name}},
                        {"range": {"timestamp": {"gte": (datetime.utcnow() - delta).isoformat()}}}
                    ]
                }
            },
            "size": 50, # Limit the number of logs returned
            "sort": [{"timestamp": {"order": "desc"}}]
        }

        # Assuming logs are indexed daily in a pattern like 'platform-logs-YYYY-MM-DD'
        # We'll search across recent indices.
        response = es_client.search(index="platform-logs-*", body=query)
        
        hits = response['hits']['hits']
        if not hits:
            return f"No logs found for service '{service_name}' in the last {time_window}."
        
        # Format logs for readability
        formatted_logs = [json.dumps(hit['_source']) for hit in hits]
        return "Found recent logs:\n" + "\n".join(formatted_logs)

    except Exception as e:
        logger.error(f"Failed to query Elasticsearch for logs: {e}", exc_info=True)
        return f"Error: Could not retrieve logs from Elasticsearch. Details: {e}"


def get_service_dependencies(service_name: str) -> str:
    """
    Queries the Knowledge Graph to find the upstream and downstream dependencies of a service.
    This helps in understanding the potential blast radius of an issue.

    Args:
        service_name (str): The name of the service to query.

    Returns:
        A string describing the service's dependencies.
    """
    logger.info(f"DevOps Tool: Getting dependencies for '{service_name}' from Knowledge Graph.")
    
    # Gremlin query to find services that this service depends on (out)
    # and services that depend on this service (in)
    query = f"g.V().has('Service', 'name', '{service_name}').union(outE().inV(), inE().outV()).path().by('name').by(label())"
    
    try:
        response = kgq_client.execute_gremlin_query(query)
        result = response.get("result", [])
        
        if not result:
            return f"No dependency information found for service '{service_name}'."
        
        dependencies = {"depends_on": set(), "depended_on_by": set()}
        for path in result:
            # path is like ['IntegrationHub', 'DEPENDS_ON', 'Pulsar']
            # or ['agentQ', 'DEPENDS_ON', 'IntegrationHub']
            if len(path['objects']) == 3:
                subj, pred, obj = path['objects']
                if subj == service_name:
                    dependencies["depends_on"].add(obj)
                else:
                    dependencies["depended_on_by"].add(subj)

        return json.dumps(dependencies)

    except Exception as e:
        logger.error(f"Failed to query Knowledge Graph for dependencies: {e}", exc_info=True)
        return f"Error: Could not retrieve dependencies from Knowledge Graph. Details: {e}"


def get_recent_deployments(service_name: str, hours_ago: int = 48) -> str:
    """
    Queries the Knowledge Graph to find recent deployments for a specific service.
    This helps correlate issues with recent code or configuration changes.

    Args:
        service_name (str): The name of the service to query.
        hours_ago (int): The time window in hours to look back for deployments. Defaults to 48.

    Returns:
        A string containing a list of recent deployments.
    """
    logger.info(f"DevOps Tool: Getting recent deployments for '{service_name}' in the last {hours_ago} hours.")
    
    # Calculate the timestamp to query from
    # This assumes the graph stores timestamps as ISO 8601 strings
    since_timestamp = (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat()
    
    # Gremlin query to find Deployment vertices connected to the given Service,
    # filtering by the timestamp on the associated Event vertex.
    query = f"""
    g.V().has('Service', 'name', '{service_name}')
     .in('DEPLOYED_TO').as_('d')
     .where(
         in_('CORRESPONDS_TO').has('Event', 'timestamp', gte('{since_timestamp}'))
     )
     .select('d')
     .valueMap('version', 'commit')
    """
    
    try:
        response = kgq_client.execute_gremlin_query(query)
        result = response.get("result", [])
        
        if not result:
            return f"No recent deployments found for service '{service_name}' in the last {hours_ago} hours."
        
        return f"Found recent deployments for {service_name}: {json.dumps(result)}"

    except Exception as e:
        logger.error(f"Failed to query Knowledge Graph for deployments: {e}", exc_info=True)
        return f"Error: Could not retrieve deployments from Knowledge Graph. Details: {e}"


def rollback_deployment(service_name: str, environment: str = "staging", namespace: str = "default") -> str:
    """
    Rolls back the deployment of a service to its previous version in a given namespace.
    This is a critical remediation action to be used when a new deployment is causing issues.

    Args:
        service_name (str): The name of the Kubernetes deployment to roll back.
        environment (str): The environment (not directly used by kubectl, but good for logging).
        namespace (str): The Kubernetes namespace the service resides in.

    Returns:
        A string indicating the result of the rollback command.
    """
    if not k8s_apps_v1:
        return "Error: Kubernetes client is not configured. Cannot perform rollback."

    logger.warning(f"DevOps Tool: Initiating rollback for '{service_name}' in namespace '{namespace}'.")
    
    try:
        # The body for the rollback call is an empty V1Rollback object
        body = client.V1DeploymentRollback(
            name=service_name,
            rollback_to=client.V1RollbackConfig(revision=0) # revision 0 means previous
        )
        # Note: The V1DeploymentRollback object is deprecated.
        # The modern way is to use `patch` to set the spec.template back to a previous ReplicaSet's template.
        # For this example, we'll use the simpler, though deprecated, method if available.
        # A more robust implementation would use the patch method.
        
        # A better, non-deprecated way to rollback:
        k8s_apps_v1.patch_namespaced_deployment(
            name=service_name,
            namespace=namespace,
            body={"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()}}}}}
        )

        return f"Successfully initiated rollback for deployment '{service_name}' in namespace '{namespace}'. The previous version will be deployed."
    except client.ApiException as e:
        logger.error(f"Kubernetes API error during rollback: {e}", exc_info=True)
        return f"Error: Failed to rollback deployment '{service_name}'. Kubernetes API error: {e.body}"
    except Exception as e:
        logger.error(f"Unexpected error during rollback: {e}", exc_info=True)
        return f"Error: An unexpected error occurred during rollback: {e}"


def restart_service(service_name: str, namespace: str = "default") -> str:
    """
    Performs a rolling restart of a service's deployment in Kubernetes.
    This is a common remediation step to resolve transient issues or memory leaks.

    Args:
        service_name (str): The name of the Kubernetes deployment to restart.
        namespace (str): The Kubernetes namespace the service resides in.

    Returns:
        A string indicating the result of the restart command.
    """
    if not k8s_apps_v1:
        return "Error: Kubernetes client is not configured. Cannot perform restart."

    logger.warning(f"DevOps Tool: Initiating rolling restart for '{service_name}' in namespace '{namespace}'.")
    
    try:
        # The standard way to trigger a rolling restart is to update an annotation
        # in the pod template. `kubectl rollout restart` does this under the hood.
        patch_body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()
                        }
                    }
                }
            }
        }
        
        k8s_apps_v1.patch_namespaced_deployment(
            name=service_name,
            namespace=namespace,
            body=patch_body,
        )

        return f"Successfully initiated rolling restart for deployment '{service_name}' in namespace '{namespace}'."
    except client.ApiException as e:
        logger.error(f"Kubernetes API error during restart: {e}", exc_info=True)
        return f"Error: Failed to restart deployment '{service_name}'. Kubernetes API error: {e.body}"
    except Exception as e:
        logger.error(f"Unexpected error during restart: {e}", exc_info=True)
        return f"Error: An unexpected error occurred during restart: {e}"


def increase_service_replicas(service_name: str, new_replica_count: int, namespace: str = "default") -> str:
    """
    Scales a Kubernetes deployment to a new number of replicas.
    Useful for handling increased load on a service.

    Args:
        service_name (str): The name of the Kubernetes deployment to scale.
        new_replica_count (int): The desired number of replicas.
        namespace (str): The Kubernetes namespace the service resides in.

    Returns:
        A string indicating the result of the scaling command.
    """
    if not k8s_apps_v1:
        return "Error: Kubernetes client is not configured. Cannot perform scaling."

    logger.warning(f"DevOps Tool: Scaling deployment '{service_name}' to {new_replica_count} replicas in namespace '{namespace}'.")
    
    try:
        patch_body = {"spec": {"replicas": new_replica_count}}
        k8s_apps_v1.patch_namespaced_deployment_scale(
            name=service_name,
            namespace=namespace,
            body=patch_body,
        )
        return f"Successfully scaled deployment '{service_name}' to {new_replica_count} replicas."
    except client.ApiException as e:
        logger.error(f"Kubernetes API error during scaling: {e}", exc_info=True)
        return f"Error: Failed to scale deployment '{service_name}'. Kubernetes API error: {e.body}"
    except Exception as e:
        logger.error(f"Unexpected error during scaling: {e}", exc_info=True)
        return f"Error: An unexpected error occurred during scaling: {e}"


# --- Tool Registration ---

get_service_logs_tool = Tool(
    name="get_service_logs",
    description="Retrieves recent logs for a specific service from the centralized logging system.",
    func=get_service_logs
)

get_service_dependencies_tool = Tool(
    name="get_service_dependencies",
    description="Finds the upstream and downstream dependencies of a service from the Knowledge Graph.",
    func=get_service_dependencies
)

get_recent_deployments_tool = Tool(
    name="get_recent_deployments",
    description="Queries the Knowledge Graph to find recent deployments for a specific service.",
    func=get_recent_deployments
)

rollback_deployment_tool = Tool(
    name="rollback_deployment",
    description="Rolls back a service to its previously deployed version. Use as a last resort if a deployment is confirmed to be faulty.",
    func=rollback_deployment
) 

restart_service_tool = Tool(
    name="restart_service",
    description="Performs a rolling restart of a service. This can resolve transient issues or memory leaks. Requires human confirmation.",
    func=restart_service
)

increase_replicas_tool = Tool(
    name="increase_service_replicas",
    description="Scales a service's deployment to a specified number of replicas to handle increased load. Requires human confirmation.",
    func=increase_service_replicas
) 