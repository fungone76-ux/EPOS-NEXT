"""Central structlog configuration and typed context binding."""

from __future__ import annotations

import logging

import structlog
from structlog.stdlib import BoundLogger

from epos.domain.logging import LogContext


def configure_structured_logging(*, json_output: bool = True) -> None:
    renderer = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def structured_logger(name: str, context: LogContext) -> BoundLogger:
    logger: BoundLogger = structlog.get_logger(name)
    return logger.bind(**context.model_dump(mode="json", exclude_none=True))
