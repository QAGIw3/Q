import logging
from pymilvus import utility, connections, Collection, CollectionSchema, FieldSchema as MilvusField, DataType
from typing import List, Dict, Any

from .config import get_config
from shared.q_vectorstore_client.models import Vector, Query, SearchHit, QueryResult
from app.api.management import CollectionSchema as ApiCollectionSchema, IndexParams

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MilvusHandler:
    """
    Handles all interactions with the Milvus vector database.
    """

    def __init__(self):
        self.config = get_config().milvus
        self.alias = self.config.alias
        self._connected = False

    def connect(self):
        """
        Establishes a connection to the Milvus server.
        """
        if self._connected and self.alias in connections.list_connections():
            logger.info("Already connected to Milvus.")
            return

        try:
            logger.info(f"Connecting to Milvus at {self.config.host}:{self.config.port}...")
            connections.connect(
                alias=self.alias,
                host=self.config.host,
                port=str(self.config.port),
                token=self.config.token
            )
            self._connected = True
            logger.info("Successfully connected to Milvus.")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}", exc_info=True)
            self._connected = False
            raise

    def disconnect(self):
        """
        Disconnects from the Milvus server.
        """
        try:
            if self.alias in connections.list_connections():
                connections.disconnect(self.alias)
                self._connected = False
                logger.info("Disconnected from Milvus.")
        except Exception as e:
            logger.error(f"Failed to disconnect from Milvus: {e}", exc_info=True)
            raise

    def create_collection_with_index(self, schema_def: ApiCollectionSchema, index_params: IndexParams) -> Dict[str, bool]:
        """
        Creates a new collection and a vector index if it doesn't already exist.

        Args:
            schema_def: The Pydantic model defining the collection schema.
            index_params: The Pydantic model defining the vector index.

        Returns:
            A dictionary indicating if the collection was created.
        """
        self.connect()
        collection_name = schema_def.collection_name
        
        if utility.has_collection(collection_name, using=self.alias):
            logger.info(f"Collection '{collection_name}' already exists.")
            return {"created": False}

        # Convert Pydantic FieldSchema to Milvus FieldSchema
        milvus_fields = []
        for f in schema_def.fields:
            field_args = {
                "name": f.name,
                "dtype": getattr(DataType, f.dtype.upper()),
                "is_primary": f.is_primary,
            }
            if f.dtype.lower() == 'varchar':
                field_args["max_length"] = f.max_length
            if f.dtype.lower() == 'float_vector':
                field_args["dim"] = f.dim
            milvus_fields.append(MilvusField(**field_args))

        # Create the Milvus CollectionSchema
        milvus_schema = CollectionSchema(
            fields=milvus_fields,
            description=schema_def.description,
            enable_dynamic_field=schema_def.enable_dynamic_field
        )

        # Create the collection
        collection = Collection(
            name=collection_name,
            schema=milvus_schema,
            using=self.alias
        )
        logger.info(f"Collection '{collection_name}' created.")

        # Create the index
        collection.create_index(
            field_name=index_params.field_name,
            index_params={
                "index_type": index_params.index_type,
                "metric_type": index_params.metric_type,
                "params": index_params.params
            }
        )
        logger.info(f"Index created on field '{index_params.field_name}' for collection '{collection_name}'.")
        return {"created": True}

    def get_collection(self, collection_name: str) -> Collection:
        """
        Retrieves a Milvus collection object, ensuring it exists.
        """
        self.connect()
        if not utility.has_collection(collection_name, using=self.alias):
            raise ValueError(f"Collection '{collection_name}' does not exist in Milvus.")
        
        collection = Collection(name=collection_name, using=self.alias)
        collection.load() # Load collection into memory for searching
        return collection

    def upsert(self, collection_name: str, vectors: List[Vector]) -> Dict[str, Any]:
        """
        Upserts a batch of vectors into the specified collection.
        """
        collection = self.get_collection(collection_name)
        
        # Milvus SDK expects lists of fields, not a list of objects
        ids = [v.id for v in vectors]
        embeddings = [v.values for v in vectors]
        metadata_list = [v.metadata for v in vectors]
        
        # This assumes the metadata keys match the scalar field names in the collection.
        # A more robust implementation might validate this.
        # For now, we assume the first metadata object has all the keys.
        data_to_insert = [embeddings]
        if metadata_list and metadata_list[0]:
            for key in metadata_list[0].keys():
                field_data = [meta.get(key) for meta in metadata_list]
                data_to_insert.append(field_data)
        
        # Milvus `insert` is actually an upsert if the primary keys already exist.
        mutation_result = collection.insert(data_to_insert)
        collection.flush()
        logger.info(f"Upserted {mutation_result.insert_count} vectors into '{collection_name}'.")
        return {"primary_keys": mutation_result.primary_keys, "insert_count": mutation_result.insert_count}


    def search(self, collection_name: str, queries: List[Query]) -> List[QueryResult]:
        """
        Performs a batch search on a collection.
        """
        collection = self.get_collection(collection_name)
        
        search_params = {
            "metric_type": "COSINE", # Should be configurable
            "params": {"nprobe": 10},
        }

        results = collection.search(
            data=[q.values for q in queries],
            anns_field="embedding", # Assumes the vector field is named "embedding"
            param=search_params,
            limit=max(q.top_k for q in queries), # Use the max top_k for the batch
            expr=None, # Placeholder for filter expressions
            output_fields=["*"] # Return all scalar fields
        )

        # Process results into our Pydantic models
        search_responses = []
        for i, hits in enumerate(results):
            query_hits = []
            for hit in hits:
                # The 'entity' field contains the scalar fields
                metadata = hit.entity.to_dict() if hasattr(hit, 'entity') else {}
                query_hits.append(SearchHit(id=hit.id, score=hit.distance, metadata=metadata))
            
            # Trim results to the specific top_k for this query
            query_hits = query_hits[:queries[i].top_k]
            search_responses.append(QueryResult(hits=query_hits))
            
        return search_responses

# Global instance for the application
milvus_handler = MilvusHandler() 