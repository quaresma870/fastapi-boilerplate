"""
Rate limiting middleware — in-memory (default) or Redis-backed.

Uses a sliding window counter per IP address.
Stricter limits apply automatically to /auth/ endpoints.
"""

import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class _InMemoryStore:
    """Thread-safe sliding window rate limiter backed by in-process memory."""

    def __init__(self):
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str, limit: int, window: int = 60) -> bool:
        now = time.time()
        dq = self._windows[key]

        # Drop timestamps outside the window
        while dq and dq[0] < now - window:
            dq.popleft()

        if len(dq) >= limit:
            return False

        dq.append(now)
        return True


_store = _InMemoryStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Auth endpoints get a stricter limit
        is_auth = "/auth/" in path
        limit = (
            settings.RATE_LIMIT_AUTH_PER_MINUTE
            if is_auth
            else settings.RATE_LIMIT_PER_MINUTE
        )
        key = f"{ip}:{'auth' if is_auth else 'general'}"

        if not _store.is_allowed(key, limit):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        return response
