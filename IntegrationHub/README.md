# Cross-Platform Integration Hub

## Overview

The Cross-Platform Integration Hub is a plug-and-play service for connecting your AI ecosystem to external APIs, databases, SaaS, and messaging platforms (such as Slack, Teams, SAP, and more). It features a no-code/low-code interface, enabling rapid, secure integration with minimal effort.

## Current Status: Proof of Concept

This service is currently in the Proof-of-Concept (PoC) stage. The foundational API server is built, and a simple flow execution engine and a PoC Slack connector have been implemented.

## Architecture

The current architecture is composed of a FastAPI-based API server, a simple core execution engine, and a system for dynamically loaded connectors.

```mermaid
graph TD
    subgraph Integration Hub Core
        API_Server["Integration API Server<br/>(Python/FastAPI)<br/>Manages flows, connectors"]
        Flow_Engine["Flow Execution Engine<br/>(Core Module)<br/>Orchestrates steps"]
        Connectors["Connectors<br/>(e.g., SlackSink)"]
    end

    API_Server -- "Triggers" --> Flow_Engine
    Flow_Engine -- "Loads & Executes" --> Connectors
```

## Getting Started

### Prerequisites

- Python 3.8+
- An active Slack account with permissions to create incoming webhooks.

### Installation

1.  **Clone the repository**
2.  **Install dependencies:**

    ```bash
    # Install main application dependencies
    pip install -r IntegrationHub/requirements.txt

    # Install development/testing dependencies
    pip install -r IntegrationHub/requirements-dev.txt
    ```

### Running the Service

The Integration Hub is powered by a FastAPI application.

1.  **Start the server:**

    ```bash
    uvicorn IntegrationHub.app.main:app --reload
    ```

2.  **Access the API documentation:**

    Once the server is running, you can access the interactive OpenAPI documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Running Tests

The project uses `pytest` for testing.

```bash
python3 -m pytest IntegrationHub/tests/
```

## API Endpoints

The following API endpoints are available:

-   `POST /flows/`: Create a new integration flow.
-   `GET /flows/`: List all existing flows.
-   `GET /flows/{flow_id}`: Retrieve a specific flow.
-   `POST /flows/{flow_id}/trigger`: Manually trigger a flow execution.
-   `GET /connectors/`: List all available connectors.

### Example: Triggering a Slack Notification Flow

1.  **Create a flow** by sending a `POST` request to `/flows/` with the following JSON body. This defines a single-step flow that uses the `slack-webhook` connector.

    ```json
    {
      "name": "Send a Slack Message",
      "trigger": {
        "type": "manual",
        "configuration": {}
      },
      "steps": [
        {
          "name": "Slack Notifier",
          "connector_id": "slack-webhook",
          "configuration": {
            "webhook_url": "YOUR_SLACK_WEBHOOK_URL",
            "message": "Hello from the Integration Hub!"
          }
        }
      ]
    }
    ```

    Replace `YOUR_SLACK_WEBHOOK_URL` with your actual Slack incoming webhook URL. Note the `id` of the flow returned in the response.

2.  **Trigger the flow** by sending a `POST` request to `/flows/{flow_id}/trigger`, where `{flow_id}` is the ID you received in the previous step.

A message "Hello from the Integration Hub!" should appear in your configured Slack channel.

## Contributing

We welcome new connectors, integrations, and UI/UX improvements. See `CONTRIBUTING.md` for details.
