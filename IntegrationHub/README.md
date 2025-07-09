# 🔌 IntegrationHub

## Overview

`IntegrationHub` is the central service for connecting the Q Platform to external systems. It provides a unified framework for building, deploying, and managing connectors that can synchronize data, trigger workflows, and bridge the gap between our internal services and third-party APIs.

The core idea is to have a single, managed service that handles the complexities of external API authentication, rate limiting, and data transformation, providing a clean and consistent interface to the rest of the Q Platform, primarily via Apache Pulsar topics.

## Architecture

1.  **FastAPI Core**: A central FastAPI application that provides API endpoints for managing connectors, credentials, and data flows.
2.  **Connector Framework**: A pluggable architecture located in `app/connectors/`. Each connector is a self-contained module responsible for the logic of interacting with a specific external API (e.g., `app/connectors/zulip/`).
3.  **Credential Management**: Uses HashiCorp Vault (via `core/vault_client.py`) to securely store and retrieve API keys and other credentials needed by the connectors.
4.  **Pulsar Integration**: The hub is designed to be event-driven. Connectors can produce data to or consume data from Pulsar topics, allowing other services like `H2M` or `agentQ` to react to external events in real-time.
5.  **Flow Engine**: The `core/engine.py` contains the logic for defining and executing data synchronization flows between connectors and internal systems.

---

## 🚀 Getting Started

### 1. Adding a New Connector

To add support for a new external system (e.g., Slack, GitHub, Jira), follow these steps:

1.  **Create a Connector Directory**: Create a new directory under `app/connectors/your_connector_name`.
2.  **Implement the Connector**: Inside this directory, create a Python file (e.g., `your_connector.py`) that contains a class inheriting from a future `BaseConnector`. This class will implement methods like `connect`, `poll`, `send_message`, etc.
3.  **Define Models**: Use Pydantic models in `app/models/` to define the data structures for the connector's configuration and data payloads.
4.  **Add API Endpoints**: Expose the connector's functionality through new endpoints in `app/api/`.

### 2. Running the Service

The service can be run like any other FastAPI application in the platform.

```bash
# Install dependencies
pip install -r IntegrationHub/requirements.txt

# Run the server (from the project root)
export PYTHONPATH=$(pwd)
uvicorn IntegrationHub.app.main:app --reload
```

## Observability

-   **Structured Logging**: The service uses `structlog` to emit JSON-formatted logs for easy parsing and analysis.
-   **Metrics**: Exposes a `/metrics` endpoint for Prometheus to scrape. It tracks standard metrics like request latency and counts.
