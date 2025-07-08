# 🧠 QuantumPulse

QuantumPulse is the next-generation service for distributed LLM inference pipelines. It is designed to be a highly scalable, message-driven system that can preprocess, route, and execute inference requests efficiently.

## Architecture

QuantumPulse is built around a decoupled, message-driven architecture using Apache Pulsar as its backbone.

1.  **API Gateway**: A FastAPI application receives inference requests and publishes them to an initial Pulsar topic.
2.  **Stream Processing (Apache Flink)**:
    *   **Prompt Optimizer**: A PyFlink job consumes raw requests, performs preprocessing (e.g., cleaning, tokenizing), and publishes them to a `preprocessed-requests` topic.
    *   **Dynamic Router**: A second PyFlink job consumes preprocessed requests and routes them to a model-and-shard-specific topic based on the request content (e.g., routing code-related questions to a specialized model).
3.  **Inference Workers**: Python services that subscribe to one or more model shard topics. They load the specified model, perform inference, and publish the result to a reply topic specified in the original request.
4.  **Real-time Reply-To Pattern**: The system uses temporary, exclusive reply topics to send the final inference result directly back to the original requester (e.g., the `H2M` service).

---

## 🚀 Getting Started

### 1. Dependencies

-   An running Apache Pulsar cluster.
-   An running Apache Flink cluster.
-   Docker (for containerized deployment).

### 2. Running the Flink Jobs

The stream processing jobs must be submitted to your Flink cluster. The `QuantumPulse/app/stream_processors/` directory contains scripts to do this.

```bash
# From the project root
export PYTHONPATH=$(pwd)

# Submit the Prompt Optimizer job
python QuantumPulse/app/stream_processors/prompt_optimizer.py

# Submit the Dynamic Router job
python QuantumPulse/app/stream_processors/router.py
```

### 3. Running the Service with Docker Compose

The easiest way to run the API server and the workers is with the provided `docker-compose.yml` file.

```bash
# From the QuantumPulse directory
cd QuantumPulse

# Start all services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 4. CI/CD

A GitHub Actions workflow is configured in `.github/workflows/quantumpulse-ci.yml`. It automatically builds and publishes the `quantumpulse-api` and `quantumpulse-worker` images to the Harbor registry on every push to `main`.