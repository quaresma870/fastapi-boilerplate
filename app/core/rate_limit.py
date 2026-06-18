"""
Rate limiting middleware — Redis-backed (production) with in-memory fallback (dev/test).

Uses a sliding window counter per IP address.
Stricter limits apply automatically to /auth/ endpoints.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

# ── In-memory store (fallback) ────────────────────────────────────────────────

class _InMemoryStore:
    """Sliding window rate limiter backed by in-process memory.
    Only suitable for single-instance deployments or testing.
    """

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str, limit: int, window: int = 60) -> bool:
        now = time.time()
        dq = self._windows[key]
        while dq and dq[0] < now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

    def clear(self) -> None:
        self._windows.clear()


# ── Redis store ───────────────────────────────────────────────────────────────

class _RedisStore:
    """Sliding window rate limiter backed by Redis.
    Safe for multi-instance deployments (multiple workers / Kubernetes pods).
    """

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(
                    self._url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=1,
                )
            except Exception:
                return None
        return self._client

    async def is_allowed_async(self, key: str, limit: int, window: int = 60) -> bool:
        client = await self._get_client()
        if client is None:
            return True  # fail open — Redis unavailable
        now = time.time()
        pipe_key = f"rl:{key}"
        try:
            async with client.pipeline() as pipe:
                pipe.zremrangebyscore(pipe_key, 0, now - window)
                pipe.zcard(pipe_key)
                pipe.zadd(pipe_key, {str(now): now})
                pipe.expire(pipe_key, window + 1)
                results = await pipe.execute()
            count = results[1]
            return count < limit
        except Exception:
            return True  # fail open on Redis error


# ── Store selection ───────────────────────────────────────────────────────────

_memory_store = _InMemoryStore()
_redis_store: _RedisStore | None = None


def _get_redis_store() -> _RedisStore | None:
    global _redis_store
    if settings.REDIS_ENABLED and _redis_store is None:
        _redis_store = _RedisStore(settings.REDIS_URL)
    return _redis_store if settings.REDIS_ENABLED else None


# ── Middleware ────────────────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        path = request.url.path

        is_auth = "/auth/" in path
        limit = (
            settings.RATE_LIMIT_AUTH_PER_MINUTE
            if is_auth
            else settings.RATE_LIMIT_PER_MINUTE
        )
        key = f"{ip}:{'auth' if is_auth else 'general'}"

        redis = _get_redis_store()
        if redis:
            allowed = await redis.is_allowed_async(key, limit)
        else:
            allowed = _memory_store.is_allowed(key, limit)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "type": "https://httpstatuses.com/429",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": "Rate limit exceeded. Please slow down.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Backend"] = "redis" if redis else "memory"
        return response
