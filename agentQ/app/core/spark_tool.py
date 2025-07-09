import logging
import yaml
from agentQ.app.core.toolbox import Tool
from kubernetes import client, config
import uuid

logger = logging.getLogger(__name__)

# --- Kubernetes Client Setup ---
try:
    config.load_incluster_config()
    k8s_custom_objects_api = client.CustomObjectsApi()
    logger.info("Successfully loaded in-cluster Kubernetes config for Spark tool.")
except config.ConfigException:
    try:
        config.load_kube_config()
        k8s_custom_objects_api = client.CustomObjectsApi()
        logger.info("Successfully loaded local kubeconfig for Spark tool.")
    except config.ConfigException:
        logger.warning("Could not configure Kubernetes client for Spark tool. Tool will not work.")
        k8s_custom_objects_api = None


def submit_spark_job(job_name: str, arguments: dict = None, namespace: str = "default") -> str:
    """
    Submits a Spark job to the Kubernetes cluster by creating a SparkApplication resource.
    Args:
        job_name (str): The name of the Spark job template to use (e.g., 'h2m-feedback-processor', 'log-pattern-analyzer').
        arguments (dict): A dictionary of arguments to pass to the Spark job.
        namespace (str): The Kubernetes namespace to run the job in.
    Returns:
        A string indicating the submission status and job ID.
    """
    if not k8s_custom_objects_api:
        return "Error: Kubernetes client not configured. Cannot submit Spark job."

    logger.info(f"Data Analyst Tool: Submitting Spark job '{job_name}' with args: {arguments}")

    # Load the base SparkApplication template
    # In a real system, these would be stored in a more structured way
    template_path = f"/app/job_templates/{job_name}.yaml"
    try:
        with open(template_path) as f:
            spark_app_manifest = yaml.safe_load(f)
    except FileNotFoundError:
        return f"Error: Spark job template '{job_name}.yaml' not found."

    # Customize the manifest
    app_name = f"{job_name}-{uuid.uuid4().hex[:8]}"
    spark_app_manifest["metadata"]["name"] = app_name
    
    # Add arguments to the Spark job spec if provided
    if arguments and "mainApplicationFile" in spark_app_manifest["spec"]:
        spark_app_manifest["spec"]["mainApplicationFile"] += [f"--{k} {v}" for k, v in arguments.items()]

    try:
        k8s_custom_objects_api.create_namespaced_custom_object(
            group="sparkoperator.k8s.io",
            version="v1beta2",
            namespace=namespace,
            plural="sparkapplications",
            body=spark_app_manifest,
        )
        return f"Successfully submitted Spark job '{job_name}' with application name '{app_name}'. Check the cluster for status."
    except client.ApiException as e:
        logger.error(f"Kubernetes API error submitting Spark job: {e}", exc_info=True)
        return f"Error: Failed to submit Spark job '{job_name}'. Kubernetes API error: {e.body}"

submit_spark_job_tool = Tool(
    name="submit_spark_job",
    description="Submits a pre-defined Spark job for large-scale data analysis (e.g., on user feedback or platform logs). Takes a job_name and an optional dictionary of arguments.",
    func=submit_spark_job
) 