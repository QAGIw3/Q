from opentelemetry import trace
from opentelemetry.propagate import inject, extract
from pulsar import Message

def inject_trace_context(message_properties: dict) -> dict:
    """Injects the current OpenTelemetry trace context into a dictionary."""
    inject(message_properties)
    return message_properties

def extract_trace_context(message: Message) -> trace.SpanContext:
    """Extracts the OpenTelemetry trace context from a Pulsar message."""
    properties = message.properties()
    return extract(properties) 