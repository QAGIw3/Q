# KnowledgeGraphQ/scripts/ingest_docs.py

import os
import httpx
import asyncio
import logging
import structlog
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import uuid

# This assumes the script is run from the root of the Q project
# and shared is in the PYTHONPATH
from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_vectorstore_client.models import Vector

# --- Configuration & Logging ---
from shared.observability.logging_config import setup_logging

setup_logging()
logger = structlog.get_logger(__name__)

VECTORSTORE_URL = "http://localhost:8001"
DATA_DIR = "KnowledgeGraphQ/data"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "rag_document_chunks"
VECTOR_DIMENSION = 384 # Based on all-MiniLM-L6-v2

# --- Schema Definition ---
RAG_COLLECTION_SCHEMA = {
    "schema": {
        "collection_name": COLLECTION_NAME,
        "description": "Chunks of documents for Retrieval-Augmented Generation.",
        "fields": [
            {"name": "chunk_id", "dtype": "VarChar", "is_primary": True, "max_length": 36},
            {"name": "document_id", "dtype": "VarChar", "max_length": 255},
            {"name": "source_name", "dtype": "VarChar", "max_length": 255},
            {"name": "text_chunk", "dtype": "VarChar", "max_length": 2000}, # Adjust size as needed
            {"name": "embedding", "dtype": "FloatVector", "dim": VECTOR_DIMENSION},
        ],
    },
    "index": {
        "field_name": "embedding",
        "index_type": "HNSW",
        "metric_type": "COSINE",
    }
}

async def create_collection_if_not_exists():
    """Calls the VectorStoreQ API to create the collection."""
    logger.info("Attempting to create collection", collection_name=COLLECTION_NAME)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VECTORSTORE_URL}/v1/manage/create-collection",
                json=RAG_COLLECTION_SCHEMA,
                timeout=30.0
            )
            response.raise_for_status()
            logger.info("Create collection response", response=response.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404: # Not found, which is unexpected here
             logger.error("Management endpoint not found", service_url=VECTORSTORE_URL)
        else:
            logger.error("Error creating collection", status=e.response.status_code, text=e.response.text)
        raise
    except httpx.RequestError as e:
        logger.error("Could not connect to VectorStoreQ", service_url=VECTORSTORE_URL, error=str(e))
        raise

def load_and_chunk_documents():
    """Loads documents from the data directory and splits them into chunks."""
    logger.info("Loading documents", data_dir=DATA_DIR)
    loader = DirectoryLoader(DATA_DIR, glob="**/*.md", loader_cls=TextLoader)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    logger.info("Finished document processing", doc_count=len(documents), chunk_count=len(chunks))
    return chunks

def generate_embeddings(chunks, model):
    """Generates vector embeddings for document chunks."""
    logger.info("Generating embeddings for all chunks...")
    sentences = [chunk.page_content for chunk in chunks]
    embeddings = model.encode(sentences, show_progress_bar=True)
    logger.info("Embedding generation complete")
    return embeddings

async def ingest_data():
    """The main ingestion pipeline."""
    # 1. Ensure the collection exists
    await create_collection_if_not_exists()

    # 2. Load and chunk documents
    chunks = load_and_chunk_documents()
    if not chunks:
        logger.warn("No documents to ingest. Exiting.")
        return

    # 3. Initialize models
    logger.info("Loading sentence transformer model", model_name=EMBEDDING_MODEL)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    vs_client = VectorStoreClient(base_url=VECTORSTORE_URL)

    # 4. Generate embeddings
    embeddings = generate_embeddings(chunks, embedding_model)

    # 5. Prepare and upsert data in batches
    vectors_to_upsert = []
    for i, chunk in enumerate(chunks):
        vector = Vector(
            id=str(uuid.uuid4()),
            values=embeddings[i].tolist(),
            metadata={
                "chunk_id": str(i), # Simple chunk ID
                "document_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.metadata['source'])),
                "source_name": os.path.basename(chunk.metadata['source']),
                "text_chunk": chunk.page_content
            }
        )
        vectors_to_upsert.append(vector)

    logger.info("Upserting vectors to VectorStoreQ", vector_count=len(vectors_to_upsert))
    try:
        await vs_client.upsert(collection_name=COLLECTION_NAME, vectors=vectors_to_upsert)
        logger.info("Ingestion process completed successfully")
    except Exception as e:
        logger.error("Failed to upsert data", error=str(e), exc_info=True)
    finally:
        await vs_client.close()


if __name__ == "__main__":
    asyncio.run(ingest_data()) 