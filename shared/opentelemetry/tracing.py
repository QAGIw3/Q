# shared/opentelemetry/tracing.py
import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

logger = logging.getLogger(__name__)

def setup_tracing(service_name: str):
    """Initializes OpenTelemetry tracing for a given service."""
    
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
    
    resource = Resource(attributes={
        "service.name": service_name
    })

    provider = TracerProvider(resource=resource)
    
    # Configure the OTLP exporter to send traces to Tempo
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Sets the global default tracer provider
    trace.set_tracer_provider(provider)
    
    logger.info(f"OpenTelemetry tracing configured for '{service_name}' to endpoint '{otlp_endpoint}'.")

    # Auto-instrument common libraries
    RequestsInstrumentor().instrument()
    
    logger.info("Requests library instrumented.")

def instrument_fastapi_app(app):
    """Instruments a FastAPI application."""
    FastAPIInstrumentor.instrument_app(app)
    logger.info("FastAPI application instrumented.")
