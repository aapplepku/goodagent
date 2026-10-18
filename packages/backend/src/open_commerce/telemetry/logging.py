"""Structured JSON logging setup."""

import logging
import sys

import structlog
from structlog.stdlib import ProcessorFormatter

from open_commerce.telemetry.redaction import redact_event


def configure_logging(level: str = "INFO") -> None:
    """Configure JSON logs with context variables."""

    level_number = logging.getLevelName(level.upper())
    if not isinstance(level_number, int):
        level_number = logging.INFO

    formatter = ProcessorFormatter(
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
        ],
        processors=[
            ProcessorFormatter.remove_processors_meta,
            redact_event,
            structlog.processors.JSONRenderer(),
        ],
    )
    root = logging.getLogger()
    root.setLevel(level_number)
    handler = next((item for item in root.handlers if item.name == "open-commerce-json"), None)
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.name = "open-commerce-json"
        root.addHandler(handler)
    for existing in root.handlers:
        existing.setFormatter(formatter)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "arq", "arq.worker"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_event,
            ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_number),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
