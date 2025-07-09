# 🧠 KnowledgeGraphQ

## Overview

The `KnowledgeGraphQ` service is responsible for both populating and providing access to the Q Platform's structured knowledge graph, which is backed by a JanusGraph database.

It has two primary functions:
1.  **Data Ingestion**: A standalone script (`scripts/build_graph.py`) populates the graph with entities and relationships from source documents.
2.  **Query API**: A FastAPI service that exposes a `/query` endpoint, allowing other services (most notably `agentQ`) to execute Gremlin queries against the graph in real-time.

This service is a cornerstone of the platform's ability to answer questions about how different pieces of information are related.

---

## Architecture

-   **Graph Database**: Uses JanusGraph, a scalable graph database that can use various backends (like Cassandra) for storage.
-   **Population Script**: `scripts/build_graph.py` is a utility that reads data files and creates vertices and edges in the graph.
-   **Query Service**: A lightweight FastAPI application that provides a RESTful interface to the Gremlin query engine.

---

## 🚀 Getting Started

### 1. Prerequisites

-   A running JanusGraph instance.
-   Python 3.9+ with dependencies installed.

### 2. Installation & Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r KnowledgeGraphQ/requirements.txt
    ```

2.  **Build the Graph**: Run the population script from the project root to build the initial graph from the data in `/data`.
    ```bash
    export PYTHONPATH=$(pwd)
    python KnowledgeGraphQ/scripts/build_graph.py
    ```

3.  **Run the Service**: Start the API server to make the graph queryable.
    ```bash
    # From the project root
    export PYTHONPATH=$(pwd)
    uvicorn KnowledgeGraphQ.app.main:app --host 0.0.0.0 --port 8083 --reload
    ```

### 3. API Usage

The service exposes a single primary endpoint:

-   `POST /query`: Accepts a JSON object with a single key, `query`, containing a raw Gremlin query string. It executes the query and returns the result.
