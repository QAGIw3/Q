from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, start_http_server, REGISTRY
from prometheus_client.exposition import generate_latest
import time
import os
import logging

logger = logging.getLogger(__name__)

# --- Prometheus Metrics Definitions ---

# A counter to track the total number of HTTP requests
REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests.",
    ["method", "path", "status_code"]
)

# A histogram to track the latency of HTTP requests
LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"]
)

# --- Standard Metrics ---

# --- Workflow Metrics ---
WORKFLOW_COMPLETED_COUNTER = Counter(
    "workflow_completed_total",
    "Total number of completed workflows",
    ["status"] # e.g., 'COMPLETED', 'FAILED'
)

WORKFLOW_DURATION_HISTOGRAM = Histogram(
    "workflow_duration_seconds",
    "Histogram of workflow execution time in seconds"
)

TASK_COMPLETED_COUNTER = Counter(
    "task_completed_total",
    "Total number of completed tasks",
    ["status"] # e.g., 'COMPLETED', 'FAILED', 'CANCELLED'
)

def setup_metrics(app: FastAPI, app_name: str):
    """
    Sets up Prometheus metrics for the FastAPI application.
    It adds middleware to track HTTP requests and starts a metrics server.
    The metrics server port is configured via the METRICS_PORT env var.
    """
    metrics_port = int(os.environ.get("METRICS_PORT", 8000))

    # Start the Prometheus metrics server in a background thread
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started for {app_name} on port {metrics_port}")

    @app.middleware("http")
    async def track_metrics(request: Request, call_next):
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # After the request is processed, record the metrics
        latency = time.time() - start_time
        path = request.url.path
        
        LATENCY.labels(method=request.method, path=path).observe(latency)
        REQUESTS.labels(method=request.method, path=path, status_code=response.status_code).inc()
        
        return response 