import os
import httpx
import asyncio
import logging
import structlog
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import uuid

from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_vectorstore_client.models import Vector
from shared.observability.logging_config import setup_logging

# --- Configuration & Logging ---
setup_logging()
logger = structlog.get_logger(__name__)

VECTORSTORE_URL = "http://localhost:8001"
# Scan the entire project root
CODE_DIR = "." 
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "code_documentation"
VECTOR_DIMENSION = 384 # Based on all-MiniLM-L6-v2

# --- Schema Definition for the new collection ---
CODE_COLLECTION_SCHEMA = {
    "schema": {
        "collection_name": COLLECTION_NAME,
        "description": "Embeddings of code chunks from the Q Platform source code.",
        "fields": [
            {"name": "chunk_id", "dtype": "VarChar", "is_primary": True, "max_length": 36},
            {"name": "file_path", "dtype": "VarChar", "max_length": 512},
            {"name": "code_chunk", "dtype": "VarChar", "max_length": 4000},
            {"name": "embedding", "dtype": "FloatVector", "dim": VECTOR_DIMENSION},
        ],
    },
    "index": {
        "field_name": "embedding",
        "index_type": "HNSW",
        "metric_type": "COSINE",
    }
}

async def create_code_collection_if_not_exists():
    """Calls the VectorStoreQ API to create the code collection."""
    logger.info("Attempting to create code collection", collection_name=COLLECTION_NAME)
    try:
        async with httpx.AsyncClient() as client:
            # This assumes a service-to-service auth token is not required for this management command,
            # or that the VectorStoreQ service is lenient for localhost calls.
            # A more secure setup would require a valid JWT.
            response = await client.post(
                f"{VECTORSTORE_URL}/v1/manage/create-collection",
                json=CODE_COLLECTION_SCHEMA,
                timeout=30.0
            )
            response.raise_for_status()
            logger.info("Create code collection response", response=response.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409: # Conflict - already exists, which is fine
            logger.warn("Code collection already exists.")
        else:
            logger.error("Error creating code collection", status=e.response.status_code, text=e.response.text)
            raise
    except httpx.RequestError as e:
        logger.error("Could not connect to VectorStoreQ", service_url=VECTORSTORE_URL, error=str(e))
        raise

def load_and_chunk_code():
    """Loads Python files from the project and splits them into chunks."""
    logger.info("Loading python files from project root", data_dir=CODE_DIR)
    
    # Use DirectoryLoader to recursively find all .py files, excluding certain directories
    loader = DirectoryLoader(
        CODE_DIR, 
        glob="**/*.py", 
        loader_cls=TextLoader,
        recursive=True,
        # Exclude directories that don't contain meaningful source code
        exclude=["**/venv", "**/__pycache__", "**/.git", "**/node_modules"]
    )
    documents = loader.load()

    # Use a splitter designed for code
    python_splitter = RecursiveCharacterTextSplitter.from_language(
        language="python", chunk_size=1000, chunk_overlap=100
    )
    chunks = python_splitter.split_documents(documents)
    logger.info("Finished code processing", doc_count=len(documents), chunk_count=len(chunks))
    return chunks

def generate_embeddings(chunks, model):
    """Generates vector embeddings for code chunks."""
    logger.info("Generating embeddings for all code chunks...")
    sentences = [chunk.page_content for chunk in chunks]
    embeddings = model.encode(sentences, show_progress_bar=True)
    logger.info("Embedding generation complete")
    return embeddings

async def main():
    """The main ingestion pipeline for source code."""
    await create_code_collection_if_not_exists()

    chunks = load_and_chunk_code()
    if not chunks:
        logger.warn("No code documents to ingest. Exiting.")
        return

    logger.info("Loading sentence transformer model", model_name=EMBEDDING_MODEL)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    vs_client = VectorStoreClient(base_url=VECTORSTORE_URL)

    embeddings = generate_embeddings(chunks, embedding_model)

    vectors_to_upsert = []
    for i, chunk in enumerate(chunks):
        vector = Vector(
            id=str(uuid.uuid4()),
            values=embeddings[i].tolist(),
            metadata={
                "file_path": chunk.metadata.get('source', 'unknown'),
                "code_chunk": chunk.page_content
            }
        )
        vectors_to_upsert.append(vector)

    logger.info("Upserting code vectors to VectorStoreQ", vector_count=len(vectors_to_upsert))
    try:
        # Upsert in batches to avoid overwhelming the service
        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i + batch_size]
            await vs_client.upsert(collection_name=COLLECTION_NAME, vectors=batch)
            logger.info(f"Upserted batch {i//batch_size + 1}")

        logger.info("Code ingestion process completed successfully")
    except Exception as e:
        logger.error("Failed to upsert data", error=str(e), exc_info=True)
    finally:
        await vs_client.close()

if __name__ == "__main__":
    asyncio.run(main()) 