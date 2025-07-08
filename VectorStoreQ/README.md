# VectorStoreQ - Centralized Vector Database Service

## Overview

VectorStoreQ is the centralized, managed vector database service for the Q Platform. Its purpose is to provide a scalable, multi-tenant store for the high-dimensional embeddings that power Retrieval-Augmented Generation (RAG), semantic search, and collaborative filtering capabilities across the entire ecosystem.

By centralizing this critical AI-native resource, we avoid data silos and ensure consistent performance and scalability for all vector search operations.

## Key Component

| Component         | Technology                               | Purpose                                                                                                                                                                                                       |
|-------------------|------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Vector Database** | [Milvus](https://milvus.io/)             | A powerful, open-source, and cloud-native vector database designed for high-performance similarity search on massive datasets. It runs on Kubernetes and provides tunable consistency and scalable architecture. |
| **Alternative**   | [Weaviate](https://weaviate.io/)         | Another excellent option, offering GraphQL APIs and a rich feature set for semantic search.                                                                                                                   |

## Architecture & Integration

1.  **Deployment**: Milvus will be deployed as a stateful application on Kubernetes via its Helm chart, managed by the `infra` Terraform configuration. It will be configured for high availability.
2.  **Data Ingestion**: Services like `KnowledgeGraphQ` will be responsible for generating embeddings (e.g., from documents or data records) and writing them into dedicated collections within Milvus. `QuantumPulse` may also have streaming pipelines that write embeddings in real-time.
3.  **Data Querying**: Services that require semantic search will query Milvus directly via its SDK.
    *   `H2M` will query it to retrieve relevant context for its RAG implementation.
    *   `KnowledgeGraphQ` will use it as a core component of its semantic search API.
    *   `managerQ` will query it to find and share agent skills or behaviors.
4.  **Multi-Tenancy**: Milvus collections will be used to enforce logical separation between different data types and domains (e.g., a collection for document chunks, another for agent skills).

## Roadmap

- Deploy a production-ready Milvus cluster.
- Define a clear schema and indexing strategy for the initial use cases (`H2M` RAG).
- Develop a small, shared Python library (`q-milvus-client`) to standardize connection and querying logic for all internal services.
- Establish backup and recovery procedures for the vector data. 