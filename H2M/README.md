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

H2M sits at the center of several other services, coordinating their capabilities to deliver a cohesive experience. The architecture now features a fully functional Retrieval-Augmented Generation (RAG) pipeline and a complete Human-in-the-Loop communication channel.

1.  **API Layer (FastAPI & WebSockets)**: Exposes a secure WebSocket endpoint for clients.
2.  **Conversation Orchestrator**: The core logic of the service.
3.  **Human Feedback Loop**:
    -   A `HumanFeedbackListener` runs in the background, consuming from a Pulsar topic where agents send clarification questions.
    -   A `ConnectionManager` tracks active user WebSocket connections.
    -   When a question for a specific conversation arrives, the listener forwards it to the correct user via their WebSocket connection.
    -   When the user replies, the API sends their answer back to a "human response" topic, which the waiting agent can then consume.

This design makes H2M the primary integration point for building intelligent, context-aware AI applications on the Q Platform.

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
The first time you run the service, the `sentence-transformers` model will be downloaded, which may take a few moments.

### 2. Configuration

The service is configured via `