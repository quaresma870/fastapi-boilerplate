"""
Prometheus metrics — HTTP request instrumentation.
Exposes /metrics endpoint in Prometheus text format.
"""

from __future__ import annotations

import time

from fastapi import Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# ── Metrics ───────────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUESTS_IN_PROGRESS = Counter(
    "http_requests_in_progress_total",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
)


def _normalise_path(path: str) -> str:
    """Replace UUIDs and numeric IDs with placeholders to avoid high cardinality."""
    import re
    path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{id}", path)
    path = re.sub(r"/\d+", "/{id}", path)
    return path


# ── Middleware ────────────────────────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip the metrics endpoint itself to avoid self-scrape noise
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = _normalise_path(request.url.path)
        start = time.monotonic()

        response = await call_next(request)

        duration = time.monotonic() - start
        status_code = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

        return response


# ── Endpoint ──────────────────────────────────────────────────────────────────

async def metrics_endpoint(_: Request) -> Response:
    """Expose Prometheus metrics in text format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
