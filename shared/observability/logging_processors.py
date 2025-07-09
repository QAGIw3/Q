from opentelemetry import trace

def add_opentelemetry_spans(logger, method_name, event_dict):
    """
    A structlog processor to add trace_id and span_id to the log record.
    """
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict 