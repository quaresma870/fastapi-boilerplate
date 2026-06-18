"""
Logging configuration — structured JSON in production, coloured in development.
"""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    is_prod = settings.ENVIRONMENT == "production"

    if is_prod:
        # JSON format for log aggregators (ELK, Datadog, etc.)
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"name":"%(name)s","message":"%(message)s"}'
        )
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s"

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "passlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
