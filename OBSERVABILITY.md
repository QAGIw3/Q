# 🔭 Observability

The Q Platform is designed with observability as a first-class citizen. A robust observability stack is crucial for operating, debugging, and scaling a complex distributed system. Our strategy is built on the three pillars of observability: Logs, Metrics, and Traces.

## 1. Structured Logging

-   **Technology**: `structlog`
-   **Format**: All Python services are configured to emit logs in a structured, JSON format. This replaces plain-text logs with machine-readable data.
-   **Benefits**: Allows for powerful, fast, and scalable log aggregation and querying. You can easily filter logs by `level`, `logger_name`, or any other field, and correlate logs from different services that are part of the same request.
-   **Implementation**: A shared configuration in `shared/observability/logging_config.py` is imported by all services to ensure consistency.

## 2. Metrics

-   **Technology**: Prometheus & Grafana
-   **How it Works**:
    1.  Core FastAPI services (`H2M`, `VectorStoreQ`, etc.) use a shared middleware from `shared/observability/metrics.py`.
    2.  This middleware automatically tracks key metrics for every API request (request counts, latency, status codes) and exposes them on a `/metrics` endpoint.
    3.  A central Prometheus instance, deployed by our Terraform configuration, is configured to automatically discover and "scrape" these `/metrics` endpoints.
    4.  Grafana is deployed and pre-configured with the Prometheus instance as a data source, ready for building dashboards.
-   **Accessing Grafana**: After running `terraform apply`, find the external IP of the Grafana service and log in with the default credentials (`admin`/`Password123`). You can then start building dashboards to visualize the performance of the Q Platform.

## 3. Distributed Tracing

-   **Technology**: OpenTelemetry
-   **How it Works**:
    1.  Services are instrumented with the OpenTelemetry SDK.
    2.  The `H2M` service initiates a "trace" for each user request.
    3.  This trace context is automatically propagated through HTTP requests and Pulsar messages to downstream services like `QuantumPulse`.
    4.  This allows you to visualize the entire, end-to-end lifecycle of a request as it travels through multiple services, making it easy to pinpoint bottlenecks and errors.
-   **Backend**: The traces are sent to an OTLP-compatible backend (e.g., Jaeger or Grafana Tempo). A Tempo deployment is included in the `infra` directory. 