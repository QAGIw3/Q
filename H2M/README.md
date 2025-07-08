# 🧠 H2M - Human-to-Machine Service

## Overview

The Human-to-Machine (H2M) service is the central conversational AI orchestrator for the Q Platform. It acts as the "brain" for user-facing interactions, managing conversation flow, retrieving context, and generating intelligent, context-aware responses by integrating with the platform's downstream services.

Its core responsibilities are:
-   Providing a secure, real-time API (WebSocket) for client applications.
-   Managing user conversation history and state.
-   Enriching user prompts with relevant external knowledge via Retrieval-Augmented Generation (RAG).
-   Orchestrating the full lifecycle of a conversational turn, from receiving a message to returning a final response.

---

## Architecture

H2M sits at the center of several other services, coordinating their capabilities to deliver a cohesive experience.

1.  **API Layer (FastAPI)**: Exposes a WebSocket endpoint to receive messages from clients. It uses the `q_auth_parser` library to ensure all connections are authenticated.
2.  **Conversation Orchestrator**: The core logic of the service. For each message, it performs the following steps:
    a.  Calls the **Context Manager** to retrieve the user's past conversation history from **Apache Ignite**.
    b.  Invokes the **RAG Module** to fetch relevant document chunks from **VectorStoreQ**.
    c.  Constructs a final, enriched prompt containing the user's query, the conversation history, and the RAG context.
    d.  Submits this prompt to **QuantumPulse** for inference by a large language model.
    e.  Receives the final response from the LLM (in this simulation, it's faked).
    f.  Saves the new user message and AI response back to the conversation history via the Context Manager.
    g.  Streams the final response back to the client over the WebSocket.

This design makes H2M the primary integration point for building user-facing AI applications on the Q Platform.

---

## 🚀 Getting Started

### Prerequisites

*   Python 3.9+
*   All downstream services (`QuantumPulse`, `VectorStoreQ`, `Apache Ignite`) are running and accessible.
*   Docker (for running the service as a container).

### 1. Installation

It is highly recommended to use a virtual environment.

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install H2M's direct dependencies
pip install -r H2M/requirements.txt

# Install the shared client libraries from the project root
pip install -e ./shared/q_auth_parser
pip install -e ./shared/q_vectorstore_client
pip install -e ./shared/q_pulse_client
```

### 2. Configuration

The service is configured via `H2M/config/h2m.yaml`. Ensure the service URLs and Ignite connection details are correct for your environment.

```yaml
services:
  quantumpulse_url: "http://localhost:8000"
  vectorstore_url: "http://localhost:8001"

ignite:
  addresses:
    - "127.0.0.1:10800"
```

### 3. Running the Service

You can run the service directly via Uvicorn for development.

```bash
# From the root of the Q project, ensure the project is in the PYTHONPATH
export PYTHONPATH=$(pwd)

# Run the server
uvicorn H2M.app.main:app --host 0.0.0.0 --port 8002 --reload
```

You can then connect to the WebSocket, but you must now provide the authenticated user's claims as a query parameter.

**Example Connection URL:**
`ws://127.0.0.1:8002/chat/ws?claims=<base64-encoded-claims>`

A simple client would need to first authenticate with Keycloak, get the JWT, extract its claims payload, base64-encode it, and then use that string to open the WebSocket connection.

---

## 🐳 Docker Deployment

A `Dockerfile` is provided to containerize the service.

1.  **Build the Image**
    ```bash
    # From the root of the Q project
    docker build -f H2M/Dockerfile -t h2m-service .
    ```

2.  **Run the Container**
    ```bash
    # This command maps the port and uses --network="host" to easily
    # connect to other services running on the host's localhost.
    docker run -p 8002:8002 --network="host" --name h2m-service h2m-service
    ```
