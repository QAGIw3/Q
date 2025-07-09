import logging
import os
import json
from typing import List, Dict, Any

from pyflink.common import WatermarkStrategy, SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.pulsar import PulsarSource, PulsarSourceBuilder, SubscriptionType
from pyflink.datastream.functions import RuntimeContext, MapFunction
import requests

# --- Configuration ---
LOG = logging.getLogger(__name__)

PULSAR_SERVICE_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://pulsar:6650")
PULSAR_ADMIN_URL = os.getenv("PULSAR_ADMIN_URL", "http://pulsar:8080")
PULSAR_TOPIC = "persistent://public/default/platform-events"
KG_API_URL = os.getenv("KG_API_URL", "http://knowledgegraphq:8000/api/v1/ingest")

# This would be a service account token fetched securely
KG_API_TOKEN = os.getenv("KG_API_TOKEN", "dummy-token-for-now")


# --- Transformation Logic ---

def event_to_graph_ops(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Transforms a single platform event into a list of graph operations.
    This is the core "business logic" of the stream processor.
    """
    ops = []
    event_type = event.get("event_type")
    source = event.get("source")
    payload = event.get("payload", {})

    if not event_type or not source:
        return []

    # Create a node for the event itself
    ops.append({
        "operation": "upsert_vertex",
        "label": "Event",
        "properties": {
            "uid": event.get("event_id"),
            "type": event_type,
            "source": source,
            "timestamp": event.get("timestamp")
        }
    })

    # --- Logic for 'flow.triggered' events ---
    if event_type == "flow.triggered" and source == "IntegrationHub":
        flow_id = payload.get("flow_id")
        user_info = payload.get("user", {})
        user_id = user_info.get("sub") # From Keycloak token

        if flow_id:
            # Vertex for the flow
            ops.append({
                "operation": "upsert_vertex",
                "label": "Flow",
                "properties": {"uid": f"flow-{flow_id}", "name": flow_id}
            })
            # Edge from event to the flow it triggered
            ops.append({
                "operation": "upsert_edge", "label": "TRIGGERED",
                "from_vertex_id": event.get("event_id"), "to_vertex_id": f"flow-{flow_id}",
                "from_vertex_label": "Event", "to_vertex_label": "Flow"
            })

        if user_id:
            # Vertex for the user
            ops.append({
                "operation": "upsert_vertex",
                "label": "User",
                "properties": {"uid": user_id, "username": user_info.get("preferred_username")}
            })
            # Edge from user to the event they initiated
            ops.append({
                "operation": "upsert_edge", "label": "INITIATED",
                "from_vertex_id": user_id, "to_vertex_id": event.get("event_id"),
                "from_vertex_label": "User", "to_vertex_label": "Event"
            })
            
    # --- Logic for 'webhook.github.pull_request' events ---
    elif event_type == "webhook.github.pull_request":
        context = payload.get("context", {})
        repo = context.get("repo")
        pr_number = context.get("pr_number")

        if repo and pr_number:
            pr_uid = f"pr-{repo}-{pr_number}"
            # Vertex for the Pull Request
            ops.append({
                "operation": "upsert_vertex",
                "label": "PullRequest",
                "properties": {
                    "uid": pr_uid,
                    "repo": repo,
                    "number": pr_number,
                    "title": context.get("pr_title"),
                    "url": context.get("pr_url")
                }
            })
            # Edge from event to the PR it concerns
            ops.append({
                "operation": "upsert_edge", "label": "CONCERNS",
                "from_vertex_id": event.get("event_id"), "to_vertex_id": pr_uid,
                "from_vertex_label": "Event", "to_vertex_label": "PullRequest"
            })

    # --- Logic for 'deployment.succeeded' events ---
    elif event_type == "deployment.succeeded":
        service_name = payload.get("service_name")
        version = payload.get("version")
        commit_hash = payload.get("commit_hash")

        if service_name and version:
            deployment_uid = f"deployment-{service_name}-{version}"
            # Vertex for the Deployment itself
            ops.append({
                "operation": "upsert_vertex",
                "label": "Deployment",
                "properties": { "uid": deployment_uid, "service": service_name, "version": version, "commit": commit_hash }
            })
            # Edge from the event to the deployment
            ops.append({
                "operation": "upsert_edge", "label": "CORRESPONDS_TO",
                "from_vertex_id": event.get("event_id"), "to_vertex_id": deployment_uid,
                "from_vertex_label": "Event", "to_vertex_label": "Deployment"
            })
            
            # Vertex for the Service that was deployed
            ops.append({
                "operation": "upsert_vertex",
                "label": "Service",
                "properties": { "uid": service_name, "name": service_name }
            })
            # Edge from the Deployment to the Service
            ops.append({
                "operation": "upsert_edge", "label": "DEPLOYED_TO",
                "from_vertex_id": deployment_uid, "to_vertex_id": service_name,
                "from_vertex_label": "Deployment", "to_vertex_label": "Service"
            })

    # --- Logic for 'incident.report.logged' events ---
    elif event_type == "incident.report.logged":
        service_name = payload.get("service_name")
        workflow_id = payload.get("workflow_id")
        
        if service_name and workflow_id:
            report_uid = f"rca-{workflow_id}"
            # Vertex for the RCA Report
            ops.append({
                "operation": "upsert_vertex",
                "label": "RCAReport",
                "properties": {
                    "uid": report_uid,
                    "service": service_name,
                    "summary": payload.get("summary"),
                    "root_cause": payload.get("root_cause"),
                    "remediation": payload.get("remediation_steps")
                }
            })
            # Edge from report to the service it concerns
            ops.append({
                "operation": "upsert_edge", "label": "DOCUMENTS",
                "from_vertex_id": report_uid, "to_vertex_id": service_name,
                "from_vertex_label": "RCAReport", "to_vertex_label": "Service"
            })
            # Edge from report to the workflow that generated it
            ops.append({
                "operation": "upsert_edge", "label": "GENERATED_BY",
                "from_vertex_id": report_uid, "to_vertex_id": workflow_id,
                "from_vertex_label": "RCAReport", "to_vertex_label": "Workflow"
            })

    return ops


# --- Flink Sink Logic ---

class KnowledgeGraphSink(MapFunction):
    """
    A MapFunction that sends graph operations to the KnowledgeGraphQ API.
    It collects records into batches to reduce HTTP request overhead.
    """
    def __init__(self, batch_size=20):
        self.batch_size = batch_size
        self.batch = []

    def open(self, runtime_context: RuntimeContext):
        LOG.info(f"Initializing KnowledgeGraphSink with batch size {self.batch_size}")

    def map(self, ops: List[Dict[str, Any]]):
        if ops:
            self.batch.extend(ops)
        
        if len(self.batch) >= self.batch_size:
            self.flush()
        
        return ops # We don't change the stream, just sink the data

    def flush(self):
        if not self.batch:
            return

        LOG.info(f"Sending batch of {len(self.batch)} operations to KnowledgeGraphQ API.")
        try:
            headers = {
                "Authorization": f"Bearer {KG_API_TOKEN}",
                "Content-Type": "application/json"
            }
            response = requests.post(KG_API_URL, json={"operations": self.batch}, headers=headers, timeout=10)
            response.raise_for_status()
            LOG.info(f"Successfully ingested batch. Status: {response.status_code}")
            self.batch.clear()
        except requests.RequestException as e:
            # In a production system, you'd add retries, dead-letter queues, etc.
            LOG.error(f"Failed to send batch to KnowledgeGraph API: {e}", exc_info=True)
            # For now, we'll clear the batch to avoid repeated failures on the same data.
            self.batch.clear()

    def close(self):
        # Flush any remaining items on shutdown
        self.flush()


# --- Flink Job Definition ---

def run_job():
    """
    The main entry point for the Flink job.
    """
    env = StreamExecutionEnvironment.get_execution_environment()
    # In a real cluster, you would set this higher.
    # env.set_parallelism(1)

    # 1. Pulsar Source
    pulsar_source = PulsarSource.builder() \
        .set_service_url(PULSAR_SERVICE_URL) \
        .set_admin_url(PULSAR_ADMIN_URL) \
        .set_start_cursor_from_earliest() \
        .set_topics(PULSAR_TOPIC) \
        .set_deserialization_schema(SimpleStringSchema()) \
        .set_subscription_name("flink-kg-processor") \
        .set_subscription_type(SubscriptionType.Shared) \
        .build()

    # 2. Create DataStream
    stream = env.from_source(
        pulsar_source,
        WatermarkStrategy.for_monotonous_timestamps(),
        "PulsarPlatformEventSource"
    )

    # 3. Transformation and Sink
    stream.map(lambda raw_json: json.loads(raw_json)) \
          .map(event_to_graph_ops) \
          .filter(lambda ops: ops is not None and len(ops) > 0) \
          .map(KnowledgeGraphSink()) \
          .name("TransformAndSendToKG")

    # 4. Execute Job
    env.execute("PlatformEventProcessor")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    run_job() 