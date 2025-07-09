from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, start_http_server, REGISTRY
import time
import os

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

def setup_metrics(app: FastAPI, app_name: str, port: int = 8000):
    """
    Sets up Prometheus metrics for a FastAPI application.
    - Adds a middleware to track request metrics.
    - Starts an HTTP server to expose the /metrics endpoint.
    """
    # This is a bit of a workaround for running the metrics server
    # in a separate thread. In a production environment with Gunicorn,
    # you might use the prometheus_client multiprocess mode.
    # See: https://github.com/prometheus/client_python#multiprocess-mode
    
    # Start the Prometheus metrics server in a daemon thread
    # The port for the metrics server should be different from the main app port
    metrics_port = int(os.environ.get("METRICS_PORT", 9091))
    start_http_server(metrics_port)
    print(f"Prometheus metrics server started on port {metrics_port}")

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

    print(f"Prometheus metrics middleware configured for {app_name}.") 