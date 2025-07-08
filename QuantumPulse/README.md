# 🧠 QuantumPulse

A next‑generation service for distributed LLM inference pipelines, built on Apache Pulsar. QuantumPulse enables real‑time prompt preprocessing, dynamic model routing, streaming updates, and much more — all at scale.

---

## Architecture Overview

QuantumPulse is built around a decoupled, message-driven architecture using Apache Pulsar as its backbone.

1.  **API Gateway**: A FastAPI application receives inference requests via a REST API. It validates the request and publishes it to a Pulsar topic.
2.  **Stream Processing (Apache Flink)**:
    *   **Prompt Optimizer**: A Flink job consumes raw requests, performs preprocessing (cleaning, tokenizing), and publishes them to a new topic.
    *   **Dynamic Router**: A second Flink job consumes preprocessed requests and routes them to the appropriate model shard topic based on the request content and system load.
3.  **Inference Workers**: These are Python services that subscribe to one or more model shard topics. They load the specified model, perform inference, and publish the result to a results topic. They are designed to be scaled horizontally.
4.  **Results Handler**: A final service consumes the inference results and delivers them back to the original client (e.g., via WebSocket or webhook).

This decoupled design allows each component to be developed, deployed, and scaled independently.

---

## 🚀 Getting Started

### Prerequisites

*   Python 3.9+
*   An running Apache Pulsar cluster.
*   (Optional) An running Apache Flink cluster for stream processing.
*   (Optional) Docker for containerized deployment.

### 1. Installation

Clone the repository and install the required dependencies. It is recommended to use a virtual environment.

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install production and development dependencies
pip install -r requirements-dev.txt
```

### 2. Configuration

The main configuration is in `config/quantumpulse.yaml`. Before running the services, ensure the Pulsar service URL and other settings are correct for your environment.

```yaml
pulsar:
  service_url: "pulsar://localhost:6650"
  # ... other settings
```

### 3. Running the API Server

The API server is the main entry point for inference requests.

```bash
# This will start the FastAPI server with auto-reload
python app/main.py
```

You can access the API documentation at `http://127.0.0.1:8000/docs`.

### 4. Running an Inference Worker

The workers are responsible for running the ML models. You can run multiple workers for different models and shards.

```bash
# Run a worker for 'model-a', handling 'shard-1'
python app/workers/specific_model_worker.py --model-name model-a --shard-id shard-1

# In a separate terminal, run a worker for another shard
python app/workers/specific_model_worker.py --model-name model-a --shard-id shard-2
```

### 5. Running Tests

The project uses `pytest` for testing.

```bash
pytest
```

---

## 🐳 Running with Docker Compose (Recommended)

The easiest way to run the service locally is with Docker Compose. This will start the API server and two workers.

**Prerequisite**: Ensure Docker is running.

```bash
# Start all services in detached mode
docker-compose up --build -d

# View logs for all services
docker-compose logs -f

# Stop and remove all containers
docker-compose down
```

The API will be available at `http://127.0.0.1:8000/docs`, and it will be able to communicate with the workers. This setup assumes you have a Pulsar instance running on `localhost:6650`.

## Manual Docker Deployment

If you prefer to manage containers individually, Dockerfiles are provided.

1.  **Build the Images**

    ```