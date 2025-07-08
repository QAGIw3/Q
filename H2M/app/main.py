import sys
import os
# Add the shared directory to the path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from typing import Optional, List

from openai import OpenAI
import anthropic
import pulsar
from pyignite import Client as IgniteClient
from fastavro import parse_schema, writer
import io
from pymilvus import Collection, connections
from sentence_transformers import SentenceTransformer
from opentelemetry import trace

# Import our shared tracing setup
from shared.opentelemetry.tracing import setup_tracing, instrument_fastapi_app

# Initialize tracing before any other imports that might be instrumented
SERVICE_NAME = "h2m-service"
setup_tracing(SERVICE_NAME)
tracer = trace.get_tracer(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("h2m")

app = FastAPI(title="H2M – Human-to-LLM Translator", version="0.1.0")
# Instrument the FastAPI app
instrument_fastapi_app(app)

# ---------------------------------------------------------------------------
# Environment / configuration helpers
# ---------------------------------------------------------------------------
PULSAR_SERVICE_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://localhost:6650")
IGNITE_HOST = os.getenv("IGNITE_HOST", "localhost")
IGNITE_PORT = int(os.getenv("IGNITE_PORT", 10800))
DEFAULT_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")  # or "anthropic"

MILVUS_ALIAS = "default"
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
KNOWLEDGE_COLLECTION = "knowledge_base"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K_RESULTS = 3 # Number of context chunks to retrieve

PULSAR_TOPIC = os.getenv("PULSAR_TOPIC", "q.h2m.prompts.intake")

# Avro schema definition for prompt messages
PROMPT_SCHEMA = {
    "namespace": "q.h2m",
    "type": "record",
    "name": "PromptMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "model", "type": "string"},
        {"name": "timestamp", "type": "long"}
    ]
}
PARSED_PROMPT_SCHEMA = parse_schema(PROMPT_SCHEMA)

# ---------------------------------------------------------------------------
# Clients (lazy)
# ---------------------------------------------------------------------------
_pulsar_client: Optional[pulsar.Client] = None
_pulsar_producer: Optional[pulsar.Producer] = None
_ignite_client: Optional[IgniteClient] = None
_openai_client: Optional[OpenAI] = None
_anthropic_client: Optional[anthropic.Anthropic] = None
_embedding_model: Optional[SentenceTransformer] = None
_milvus_collection: Optional[Collection] = None


def get_pulsar_producer() -> pulsar.Producer:
    global _pulsar_client, _pulsar_producer
    if _pulsar_producer is None:
        _pulsar_client = pulsar.Client(PULSAR_SERVICE_URL)
        _pulsar_producer = _pulsar_client.create_producer(PULSAR_TOPIC, schema=pulsar.schema.BytesSchema())
    return _pulsar_producer


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_milvus_collection() -> Collection:
    global _milvus_collection
    if _milvus_collection is None:
        try:
            if not connections.has_connection(MILVUS_ALIAS):
                connections.connect(MILVUS_ALIAS, host=MILVUS_HOST, port=MILVUS_PORT)
                logger.info(f"Connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
            _milvus_collection = Collection(KNOWLEDGE_COLLECTION)
            _milvus_collection.load() # Load collection into memory for searching
            logger.info(f"Successfully loaded Milvus collection: {KNOWLEDGE_COLLECTION}")
        except Exception as e:
            logger.error(f"Failed to get Milvus collection: {e}")
            raise
    return _milvus_collection


def get_ignite_cache():
    global _ignite_client
    if _ignite_client is None:
        _ignite_client = IgniteClient()
        _ignite_client.connect(IGNITE_HOST, IGNITE_PORT)
    cache = _ignite_client.get_or_create_cache("h2m_prompt_cache")
    return cache


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client


def get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class IntentRequest(BaseModel):
    intent: str
    provider: Optional[str] = None  # "openai" or "anthropic"

class PromptResponse(BaseModel):
    prompt: str
    provider: str
    cached: bool = False
    retrieved_context: Optional[List[str]] = None

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def build_rag_prompt(intent: str, context_chunks: List[str]) -> str:
    """Builds a prompt incorporating retrieved context."""
    if not context_chunks:
        return f"You are a helpful assistant. Please answer the following question: {intent}"

    context = "\n---\n".join(context_chunks)
    return (
        "You are an expert assistant. Use the following context to answer the question. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {intent}"
    )


@tracer.start_as_current_span("search_knowledge_base_span")
def search_knowledge_base(intent_vector: List[float]) -> List[str]:
    """Searches Milvus for relevant document chunks."""
    current_span = trace.get_current_span()
    current_span.set_attribute("milvus.collection", KNOWLEDGE_COLLECTION)
    current_span.set_attribute("milvus.top_k", TOP_K_RESULTS)
    
    try:
        collection = get_milvus_collection()
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10},
        }
        results = collection.search(
            data=[intent_vector],
            anns_field="vector",
            param=search_params,
            limit=TOP_K_RESULTS,
            output_fields=["text"]
        )
        context = [hit.entity.get("text") for hit in results[0]]
        current_span.set_attribute("milvus.results_count", len(context))
        return context
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        current_span.record_exception(e)
        current_span.set_status(trace.Status(trace.StatusCode.ERROR, "Milvus search failed"))
        return []

# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------
@app.post("/translate", response_model=PromptResponse)
@tracer.start_as_current_span("h2m_translate_endpoint")
async def translate(req: IntentRequest):
    provider = req.provider or DEFAULT_PROVIDER
    cache = get_ignite_cache()
    cache_key = f"{provider}:{req.intent}"

    cached_prompt = cache.get(cache_key)
    if cached_prompt:
        trace.get_current_span().set_attribute("cache.hit", True)
        return PromptResponse(prompt=cached_prompt, provider=provider, cached=True, retrieved_context=[])
    
    trace.get_current_span().set_attribute("cache.hit", False)

    # 1. Generate embedding for the intent
    with tracer.start_as_current_span("generate_intent_embedding") as span:
        model = get_embedding_model()
        intent_vector = model.encode(req.intent).tolist()
        span.set_attribute("embedding.vector_size", len(intent_vector))

    # 2. Search for relevant context in Milvus
    retrieved_context = search_knowledge_base(intent_vector)

    # 3. Build the final prompt
    with tracer.start_as_current_span("build_final_prompt"):
        prompt = build_rag_prompt(req.intent, retrieved_context)

    # 4. Store final prompt in cache
    with tracer.start_as_current_span("save_to_cache"):
        cache.put(cache_key, prompt)

    # 5. Produce message to Pulsar
    with tracer.start_as_current_span("publish_to_pulsar") as span:
        producer = get_pulsar_producer()
        message_dict = {
            "id": cache_key,
            "prompt": prompt,
            "model": provider,
            "timestamp": int(__import__("time").time() * 1000)
        }
        span.set_attribute("pulsar.topic", PULSAR_TOPIC)
        span.set_attribute("message.id", cache_key)
        buf = io.BytesIO()
        writer(buf, PARSED_PROMPT_SCHEMA, [message_dict])
        producer.send(buf.getvalue())

    return PromptResponse(
        prompt=prompt,
        provider=provider,
        cached=False,
        retrieved_context=retrieved_context
    )

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
@app.on_event("shutdown")
def shutdown_event():
    if _pulsar_client:
        _pulsar_client.close()
    if _ignite_client:
        _ignite_client.close()
    if connections.has_connection(MILVUS_ALIAS):
        connections.disconnect(MILVUS_ALIAS) 