# 🧠 managerQ

## Overview

`managerQ` is the control plane for the Q Platform's multi-agent system. It acts as a centralized dispatcher and coordinator, making the pool of autonomous `agentQ` workers a usable and scalable resource for the rest of the platform.

Its core responsibilities are:
-   **Agent Discovery**: Maintaining a real-time registry of all active and available `agentQ` instances.
-   **Task Dispatching**: Providing a single, unified API for other services to submit tasks to the agent pool.
-   **Load Balancing**: Distributing incoming tasks across the available agents (currently using a simple random strategy).
-   **Result Correlation**: Listening for results from agents and correlating them back to the original request.

## Architecture

`managerQ` is a FastAPI service that uses several background threads to manage its state and communicate over Pulsar.

1.  **API Layer**: Exposes a single REST endpoint (`POST /v1/tasks`) for submitting a new task (e.g., a prompt for an agent).
2.  **`AgentRegistry`**: A background thread consumes from the `q.agentq.registrations` topic. When an `agentQ` instance starts, it publishes a registration message. The registry adds it to an in-memory list of active agents.
3.  **`TaskDispatcher`**: When a request comes into the API, the dispatcher gets an available agent from the registry and publishes the task message directly to that agent's unique task topic.
4.  **`ResultListener`**: A second background thread consumes from the shared `q.agentq.results` topic. When it receives a result, it uses a `Future` to notify the original API request handler that the task is complete.
5.  **Request/Reply Flow**: The API handler blocks until the `ResultListener` receives the corresponding result or a timeout occurs, then returns the final answer to the client.

---

## 🚀 Getting Started

### 1. Prerequisites

-   An running Apache Pulsar cluster.
-   At least one running `agentQ` instance.

### 2. Installation & Configuration

1.  **Install Dependencies**: From the project root, install the required packages.

    ```bash
    pip install -r managerQ/requirements.txt
    ```

2.  **Configure the Manager**: The service is configured via `managerQ/config/manager.yaml`. Ensure the Pulsar service URL and topic names are correct.

### 3. Running the Service

The service can be run directly via Uvicorn for development.

```bash
# From the project root
export PYTHONPATH=$(pwd)

# Run the server
uvicorn managerQ.app.main:app --reload
```

The API documentation will be available at `http://127.0.0.1:8003/docs`.

### 4. Submitting a Task

You can submit a task to an agent via the `/v1/tasks` endpoint:

```bash
curl -X POST "http://localhost:8003/v1/tasks" \
-H "Content-Type: application/json" \
-d '{
  "prompt": "What is the capital of France, and what is its population?"
}'
```
