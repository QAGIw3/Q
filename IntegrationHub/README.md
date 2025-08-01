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

### 1. Available Connectors

-   **`zulip-message`**: Sends a message to a Zulip stream.
-   **`smtp-email`**: Sends an email via a standard SMTP server.

### 2. Adding a New Connector

To add support for a new external system (e.g., Slack, GitHub, Jira), follow these steps:

1.  **Create a Connector Directory**: Create a new directory under `app/connectors/your_connector_name`.
2.  **Implement the Connector**: Inside this directory, create a Python file (e.g., `your_connector.py`) that contains a class inheriting from a future `BaseConnector`. This class will implement methods like `connect`, `poll`, `send_message`, etc.
3.  **Define Models**: Use Pydantic models in `app/models/` to define the data structures for the connector's configuration and data payloads.
4.  **Add API Endpoints**: Expose the connector's functionality through new endpoints in `app/api/`.

### 3. Example: Triggering the "Send Email" Flow

The hub comes with a pre-defined flow with the ID `send-summary-email`. An agent can trigger this flow to send an email.

1.  **Create a Credential**: First, you must store your SMTP credentials securely in Vault. The `IntegrationHub` expects a credential with the ID `smtp-credentials`.
2.  **Trigger the Flow**: An agent can then use its `trigger_integration_flow` tool with the following parameters:
    ```json
    {
      "flow_id": "send-summary-email",
      "parameters": {
        "to": "recipient@example.com",
        "subject": "Summary from the Q Platform Agent",
        "body": "<p>This is the summary generated by the agent.</p>"
      }
    }
    ```
This will cause the `IntegrationHub` to execute the flow, load the SMTP credentials, and send the email with the content provided by the agent.

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

## Automated Code Review Agent

A key feature of the IntegrationHub is its ability to orchestrate a fully automated code review process. This is accomplished via the `code_review_agent` flow, which is triggered by GitHub webhooks.

### How It Works

1.  **Webhook Trigger**: A GitHub repository is configured to send `pull_request` events to the IntegrationHub's `/api/v1/webhooks/github` endpoint.
2.  **Signature Verification**: The endpoint securely verifies the webhook signature using a shared secret stored in Vault (`github-webhook-secret`).
3.  **Flow Execution**: A valid webhook triggers the `code_review_agent` flow, which:
    a.  Fetches the pull request's diff using the `GitHubConnector`.
    b.  Sends the diff to `agentQ` via `managerQ` with a prompt asking for a code review.
    c.  Receives the agent's review and posts it as a comment on the original pull request.

### Setup Instructions

To enable the code review agent for a repository, follow these steps:

1.  **Create Credentials in Vault**:
    *   **`github-pat`**: A credential containing a GitHub Personal Access Token with `repo` scope. The secret data should be `{"personal_access_token": "YOUR_PAT"}`.
    *   **`github-webhook-secret`**: A credential containing a long, random string to use as the webhook secret. The secret data should be `{"token": "YOUR_SECRET_STRING"}`.
    *   **`managerq-service-token`**: A credential containing a valid JWT for the `managerQ` service.

2.  **Configure the GitHub Webhook**:
    *   In your GitHub repository, go to `Settings` > `Webhooks` > `Add webhook`.
    *   **Payload URL**: `https://<your-integrationhub-host>/api/v1/webhooks/github`
    *   **Content type**: `application/json`
    *   **Secret**: Enter the same secret string you stored in the `github-webhook-secret` credential.
    *   **Which events would you like to trigger this webhook?**: Select "Let me select individual events." and check `Pull requests`.
    *   Ensure the webhook is active.

Once configured, any new pull request will automatically trigger the AI code review process.

## Concepts

The IntegrationHub is built around a few core concepts:
