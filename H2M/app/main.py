from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from typing import Optional

from openai import OpenAI
import anthropic
import pulsar
from pyignite import Client as IgniteClient
from fastavro import parse_schema, writer
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("h2m")

app = FastAPI(title="H2M – Human-to-LLM Translator", version="0.1.0")

# ---------------------------------------------------------------------------
# Environment / configuration helpers
# ---------------------------------------------------------------------------
PULSAR_SERVICE_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://localhost:6650")
IGNITE_HOST = os.getenv("IGNITE_HOST", "localhost")
IGNITE_PORT = int(os.getenv("IGNITE_PORT", 10800))
DEFAULT_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")  # or "anthropic"

PULSAR_TOPIC = os.getenv("PULSAR_TOPIC", "q.h2m.prompts")

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


def get_pulsar_producer() -> pulsar.Producer:
    global _pulsar_client, _pulsar_producer
    if _pulsar_producer is None:
        _pulsar_client = pulsar.Client(PULSAR_SERVICE_URL)
        _pulsar_producer = _pulsar_client.create_producer(PULSAR_TOPIC, schema=pulsar.schema.BytesSchema())
    return _pulsar_producer


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

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def build_prompt(intent: str) -> str:
    """Very simple placeholder prompt builder."""
    return f"You are a helpful assistant. {intent}"

# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------
@app.post("/translate", response_model=PromptResponse)
async def translate(req: IntentRequest):
    provider = req.provider or DEFAULT_PROVIDER
    cache = get_ignite_cache()
    cache_key = f"{provider}:{req.intent}"

    cached_prompt = cache.get(cache_key)
    if cached_prompt:
        return PromptResponse(prompt=cached_prompt, provider=provider, cached=True)

    # Build prompt
    prompt = build_prompt(req.intent)

    # Optionally do a quick token count with provider to adjust (skipped for brevity)

    # Store in cache
    cache.put(cache_key, prompt)

    # Produce message to Pulsar
    producer = get_pulsar_producer()
    message_dict = {
        "id": cache_key,
        "prompt": prompt,
        "model": provider,
        "timestamp": int(__import__("time").time() * 1000)
    }
    buf = io.BytesIO()
    writer(buf, PARSED_PROMPT_SCHEMA, [message_dict])
    producer.send(buf.getvalue())

    return PromptResponse(prompt=prompt, provider=provider, cached=False)

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
@app.on_event("shutdown")
def shutdown_event():
    if _pulsar_client:
        _pulsar_client.close()
    if _ignite_client:
        _ignite_client.close() 