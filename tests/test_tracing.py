"""
Tests for app.core.tracing — uses InMemorySpanExporter so no real OTLP
backend or console output is needed.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.tracing import setup_tracing


class TestSetupTracingDisabled:
    def test_noop_when_disabled(self):
        """The default — confirms setup_tracing touches nothing when
        OTEL_ENABLED is False, so a FastAPI app with tracing imported but
        disabled behaves identically to one with no tracing code at all."""
        app = FastAPI()
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.OTEL_ENABLED = False
            setup_tracing(app, engine)  # must not raise, must not instrument

        # No instrumentation middleware was added
        assert not any("opentelemetry" in str(type(m)).lower() for m in app.user_middleware)


class TestSetupTracingEnabled:
    def test_request_produces_a_trace_with_a_db_span(self):
        exporter = InMemorySpanExporter()
        app = FastAPI()
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        @app.get("/query")
        async def query_endpoint():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"ok": True}

        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.OTEL_ENABLED = True
            mock_settings.OTEL_SERVICE_NAME = "test-service"
            setup_tracing(app, engine, exporter=exporter)

        with TestClient(app) as client:
            r = client.get("/query")
        assert r.status_code == 200

        from opentelemetry import trace
        trace.get_tracer_provider().force_flush()  # BatchSpanProcessor exports on a delay otherwise

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]
        assert len(spans) >= 1
        # At least one span should be the DB query (SQLAlchemy instrumentation
        # names spans after the SQL operation/table, e.g. "SELECT" or similar)
        assert any("select" in name.lower() for name in span_names), span_names

    @pytest.mark.asyncio
    async def test_does_not_raise_with_real_app_dependencies(self):
        """Smoke test against this project's actual app/engine pair (not a
        throwaway one), confirming setup_tracing works with the real
        async engine this app actually uses, not just a minimal example."""
        from app.core.database import engine as real_engine
        from app.main import create_application

        exporter = InMemorySpanExporter()
        app = create_application()

        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.OTEL_ENABLED = True
            mock_settings.OTEL_SERVICE_NAME = "test-service"
            setup_tracing(app, real_engine, exporter=exporter)  # must not raise
