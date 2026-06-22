"""
Distributed tracing via OpenTelemetry — instruments FastAPI request handling
and SQLAlchemy queries, so a single request's trace shows where time is
actually spent (a DB query vs. an external call vs. business logic), and so
a request can be followed across service boundaries in a real deployment.

Fully optional, gated by OTEL_ENABLED (mirrors this project's established
REDIS_ENABLED-style pattern): with it disabled, setup_tracing() is a no-op
and the app behaves identically to having no tracing code at all. The
opentelemetry packages are still installed (requirements.txt) but never
imported at runtime unless tracing is actually turned on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine


def setup_tracing(app: FastAPI, engine: AsyncEngine, exporter=None) -> None:
    """exporter is an injection point for tests (e.g. InMemorySpanExporter) —
    real callers never pass it; the OTLP/console choice below is what
    actually runs in production."""
    if not settings.OTEL_ENABLED:
        return

    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    if exporter is None:
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        else:
            exporter = ConsoleSpanExporter()  # sane default — works with zero extra infra

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    # AsyncEngine wraps a sync Engine that SQLAlchemy's event system (which
    # this instrumentation hooks into) actually operates on — instrument
    # that, not the async wrapper itself.
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=provider)
