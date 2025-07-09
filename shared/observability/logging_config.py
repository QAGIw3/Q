import logging
import sys
import os
import structlog
from structlog.types import Processor
from typing import List, Optional

from .pulsar_logging import PulsarLogHandler

def setup_logging(log_level: str = "INFO", service_name: Optional[str] = None):
    """
    Configures structured, JSON-formatted logging for an application.
    Optionally adds a Pulsar handler to stream logs.
    """
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    
    # Add Pulsar handler if configured
    if os.environ.get("LOGS_TO_PULSAR", "false").lower() == "true":
        if not service_name:
            raise ValueError("service_name must be provided when LOGS_TO_PULSAR is enabled.")
        pulsar_topic = os.environ.get("PULSAR_LOG_TOPIC", "persistent://public/default/platform-logs")
        pulsar_handler = PulsarLogHandler(topic=pulsar_topic, service_name=service_name)
        handlers.append(pulsar_handler)
        print(f"Streaming logs for service '{service_name}' to Pulsar topic '{pulsar_topic}'.")

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=handlers,
    )

    # Define the structlog processor chain
    processors: List[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Render the final log message as JSON
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()
    logger.info("Structured logging configured successfully.") 