# shared/opentelemetry/tracing.py
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def setup_tracing(app, service_name: str, otlp_endpoint: str = "http://localhost:4317"):
    """
    Configures OpenTelemetry tracing for a FastAPI application.

    Args:
        app: The FastAPI app instance to instrument.
        service_name (str): The name of the service for resource attributes.
        otlp_endpoint (str): The OTLP gRPC endpoint for the collector.
    """
    if not otlp_endpoint:
        logging.getLogger(__name__).warning("OTLP_ENDPOINT not set, tracing is disabled.")
        return

    resource = Resource(attributes={"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    # Use OTLPSpanExporter for gRPC
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    if app:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        logging.getLogger(__name__).info(f"Tracing enabled for service '{service_name}' sending to '{otlp_endpoint}'.")

def get_tracer(name: str):
    return trace.get_tracer(name)
