# shared/opentelemetry/tracing.py
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from app.core.config import config

logger = logging.getLogger(__name__)

def setup_tracing(app):
    """
    Sets up OpenTelemetry tracing for the FastAPI application.
    """
    if not config.otel.enabled:
        logger.info("OpenTelemetry tracing is disabled.")
        return

    logger.info("Setting up OpenTelemetry tracing...")

    # Create a resource to identify the service
    resource = Resource(attributes={
        "service.name": config.service_name,
        "service.version": config.version,
    })

    # Set up the tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Configure the OTLP exporter
    exporter = OTLPSpanExporter(endpoint=config.otel.endpoint, insecure=True)
    
    # Use a batch processor to send spans in batches
    span_processor = BatchSpanProcessor(exporter)
    tracer_provider.add_span_processor(span_processor)

    # Instrument the FastAPI application if it's provided
    if app:
        FastAPIInstrumentor.instrument_app(app)

    logger.info(f"OpenTelemetry tracing enabled. Exporting to {config.otel.endpoint}.")
