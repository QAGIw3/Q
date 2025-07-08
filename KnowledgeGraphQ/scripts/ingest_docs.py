# KnowledgeGraphQ/scripts/ingest_docs.py

import os
import logging
from pymilvus import connections, utility, FieldSchema, CollectionSchema, DataType, Collection
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# --- Configuration ---
LOG_LEVEL = "INFO"
MILVUS_ALIAS = "default"
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")

# Collection details
COLLECTION_NAME = "knowledge_base"
ID_FIELD = "id"
DOC_SOURCE_FIELD = "doc_source"
TEXT_FIELD = "text"
VECTOR_FIELD = "vector"

# Text processing
CHUNK_SIZE = 512  # The size of text chunks in characters
CHUNK_OVERLAP = 64

# Embedding model
MODEL_NAME = "all-MiniLM-L6-v2" # A good default model

# --- Logging ---
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Main Script ---

def connect_to_milvus():
    """Establish a connection to the Milvus server."""
    try:
        connections.connect(MILVUS_ALIAS, host=MILVUS_HOST, port=MILVUS_PORT)
        logger.info(f"Successfully connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
    except Exception as e:
        logger.error(f"Failed to connect to Milvus: {e}")
        raise

def create_collection_if_not_exists(model) -> Collection:
    """Create a Milvus collection if it doesn't already exist."""
    if utility.has_collection(COLLECTION_NAME):
        logger.info(f"Collection '{COLLECTION_NAME}' already exists.")
        return Collection(COLLECTION_NAME)

    logger.info(f"Collection '{COLLECTION_NAME}' does not exist. Creating...")
    # Define fields
    # We use a varchar for the primary key to store a meaningful ID
    id_field = FieldSchema(name=ID_FIELD, dtype=DataType.VARCHAR, is_primary=True, max_length=1024)
    doc_source_field = FieldSchema(name=DOC_SOURCE_FIELD, dtype=DataType.VARCHAR, max_length=1024)
    text_field = FieldSchema(name=TEXT_FIELD, dtype=DataType.VARCHAR, max_length=65535) # Max length for VARCHAR
    vector_field = FieldSchema(name=VECTOR_FIELD, dtype=DataType.FLOAT_VECTOR, dim=model.get_sentence_embedding_dimension())

    schema = CollectionSchema(
        fields=[id_field, doc_source_field, text_field, vector_field],
        description="Knowledge Base for Q Platform",
        enable_dynamic_field=False
    )
    collection = Collection(name=COLLECTION_NAME, schema=schema)
    
    # Create an index for the vector field
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index(VECTOR_FIELD, index_params)
    logger.info(f"Successfully created collection '{COLLECTION_NAME}' and index.")
    return collection

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Splits text into overlapping chunks."""
    start = 0
    while start < len(text):
        end = start + size
        yield text[start:end]
        start += size - overlap

def ingest_data():
    """Main function to run the data ingestion process."""
    try:
        connect_to_milvus()
        
        logger.info(f"Loading sentence transformer model: '{MODEL_NAME}'")
        model = SentenceTransformer(MODEL_NAME)
        
        collection = create_collection_if_not_exists(model)
        
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        if not os.path.exists(data_dir):
            logger.error(f"Data directory not found at: {data_dir}")
            return
            
        files_to_ingest = [f for f in os.listdir(data_dir) if f.endswith((".md", ".txt"))]
        
        logger.info(f"Found {len(files_to_ingest)} files to ingest from '{data_dir}'")
        
        total_chunks = 0
        for filename in tqdm(files_to_ingest, desc="Ingesting files"):
            filepath = os.path.join(data_dir, filename)
            with open(filepath, 'r') as f:
                content = f.read()

            chunks = list(chunk_text(content))
            embeddings = model.encode(chunks)
            
            entities = []
            for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
                # Create a unique, deterministic ID for each chunk
                pk = f"{filename}-{i}"
                entities.append({
                    ID_FIELD: pk,
                    DOC_SOURCE_FIELD: filename,
                    TEXT_FIELD: chunk,
                    VECTOR_FIELD: vector
                })
            
            # Insert data
            collection.insert(entities)
            total_chunks += len(entities)
            
        # Flush to make data searchable
        collection.flush()
        logger.info("Flushed data to Milvus.")
        
        logger.info(f"Successfully ingested {total_chunks} chunks from {len(files_to_ingest)} files.")
        logger.info(f"Collection '{COLLECTION_NAME}' now contains {collection.num_entities} entities.")

    except Exception as e:
        logger.error(f"An error occurred during ingestion: {e}")
    finally:
        if connections.has_connection(MILVUS_ALIAS):
            connections.disconnect(MILVUS_ALIAS)
            logger.info("Disconnected from Milvus.")

if __name__ == "__main__":
    ingest_data() 