# 🧠 KnowledgeGraphQ

## Overview

The `KnowledgeGraphQ` service is responsible for batch processing and data ingestion pipelines that populate the Q Platform's core data services. Its primary role is to feed the `VectorStoreQ` with the high-quality embeddings needed for Retrieval-Augmented Generation (RAG).

While the name implies a future capability of building a formal knowledge graph, its current, implemented functionality is focused on the **vector database ingestion pipeline**.

---

## Data Ingestion Pipeline

The core of this service is the `scripts/ingest_docs.py` script. It performs the following steps:

1.  **Create Collection**: It first communicates with the `VectorStoreQ` API to programmatically create the necessary collection (`rag_document_chunks`) and configure its schema and vector index.
2.  **Load Documents**: It scans the `KnowledgeGraphQ/data/` directory for text-based documents (e.g., `.md`, `.txt`).
3.  **Chunk Documents**: It uses the `langchain` library to split the documents into smaller, overlapping chunks suitable for embedding.
4.  **Generate Embeddings**: It uses a `sentence-transformers` model to convert each text chunk into a vector embedding.
5.  **Ingest Data**: Finally, it uses the `q_vectorstore_client` to batch-upload the chunks, their embeddings, and associated metadata to `VectorStoreQ`.

---

## 🚀 Getting Started

### 1. Prerequisites

-   A running instance of `VectorStoreQ`.
-   Python 3.9+ with dependencies installed.

### 2. Installation

Install the necessary dependencies from the project root. It is recommended to use a virtual environment.

```bash
# Install dependencies
pip install -r KnowledgeGraphQ/requirements.txt

# Install the shared client library
pip install -e ./shared/q_vectorstore_client
```

### 3. Add Data

Place the markdown or text files you want to ingest into the `KnowledgeGraphQ/data/` directory. Two example files are already present.

### 4. Run the Ingestion Script

Execute the script from the **root directory of the Q project** to ensure correct path resolution.

```bash
export PYTHONPATH=$(pwd)
python KnowledgeGraphQ/scripts/ingest_docs.py
```

The script will log its progress as it creates the collection, chunks the documents, generates embeddings, and ingests the data into the vector store.
