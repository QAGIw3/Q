# 🚀 VectorStoreQ - Centralized Vector Database Service

## Overview

VectorStoreQ is the centralized, managed vector database service for the Q Platform. It provides a robust, scalable, and secure API for ingesting and searching the high-dimensional embeddings that power Retrieval-Augmented Generation (RAG), semantic search, and other AI-native capabilities across the platform.

By centralizing access through a dedicated service, we abstract away the underlying database technology (Milvus), enforce a consistent API contract, and manage concerns like scalability, security, and collection management in one place.

---

## Architecture

The `VectorStoreQ` ecosystem consists of two main components:

1.  **`VectorStoreQ` Service**: A FastAPI microservice that acts as the sole gatekeeper to the Milvus database cluster. It manages connections, handles data validation, and exposes high-level endpoints for search and ingestion.
2.  **`q_vectorstore_client` Library**: A shared Python library located in `shared/q_vectorstore_client`. All other services in the Q Platform **must** use this client to interact with `VectorStoreQ`. This ensures consistency, type safety, and simplifies service-to-service communication.

This architecture prevents other services from needing to know the details of the Milvus implementation, such as its connection details or the `pymilvus` SDK.

---

## 🚀 Getting Started

### Prerequisites

*   Python 3.9+
*   An running Milvus cluster. For local development, you can use the [Milvus Lite Docker container](https://milvus.io/docs/install_standalone-docker.md).
*   Docker (for running the service as a container).

### 1. Installation

It is recommended to use a virtual environment. The dependencies for the service and the client are separate.

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies for the VectorStoreQ service
pip install -r VectorStoreQ/requirements.txt
```

To use the client in another service (e.g., `H2M`), you would typically install it in editable mode:
```bash
# From the root of the Q project
pip install -e ./shared/q_vectorstore_client
```

### 2. Configuration

The service is configured via `VectorStoreQ/config/vectorstore.yaml`. Ensure the `milvus` host and port point to your running cluster.

```yaml
milvus:
  host: "localhost"
  port: 19530
```

### 3. Running the Service

You can run the service directly via Uvicorn for development.

```bash
# From the root of the Q project, add the project to the PYTHONPATH
export PYTHONPATH=$(pwd)

# Run the server
uvicorn VectorStoreQ.app.main:app --host 0.0.0.0 --port 8001 --reload
```

The API documentation will be available at `http://127.0.0.1:8001/docs`.

---

## 🐳 Docker Deployment

A `Dockerfile` is provided to containerize the service.

1.  **Build the Image**
    ```bash
    # From the root of the Q project
    docker build -f VectorStoreQ/Dockerfile -t vectorstore-q .
    ```

2.  **Run the Container**
    ```bash
    # This command maps the port and uses --network="host" to easily
    # connect to a Milvus instance running on the host's localhost.
    docker run -p 8001:8001 --network="host" --name vectorstore-q vectorstore-q
    ```

---

## API Endpoints

The service provides the following versioned API endpoints. All endpoints require a valid JWT from an authenticated user, passed via the Istio gateway.

### Ingestion

*   `POST /v1/ingest/upsert`
    *   **Purpose**: Inserts or updates a batch of vectors in a specified collection.
    *   **Authorization**: Requires a role of `admin` or `service-account`.
    *   **Request Body**: `UpsertRequest` (see `q_vectorstore_client/models.py`)
    *   **Response**: A confirmation with the number of inserted records and their primary keys.

### Search

*   `POST /v1/search`
    *   **Purpose**: Performs a batch similarity search across one or more query vectors.
    *   **Authorization**: Requires any authenticated user role.
    *   **Request Body**: `SearchRequest` (see `q_vectorstore_client/models.py`)
    *   **Response**: `SearchResponse`, containing a list of hits for each query. 