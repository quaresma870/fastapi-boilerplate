"""
Background task queue — moves slow operations (sending email, etc.) out of
the request/response path.

Uses arq (Redis-backed) when Redis is enabled, mirroring this project's
established REDIS_ENABLED-gated degradation pattern already used for rate
limiting and the token denylist (see core/rate_limit.py, core/security.py).
Falls back to FastAPI's own BackgroundTasks when Redis isn't available —
this never becomes a hard Redis requirement.

The one real difference between the two paths: an arq job survives a
process restart (it's durable in Redis until a worker picks it up);
BackgroundTasks does not (if the process dies before it runs, the task is
lost). That's an accepted, documented tradeoff for the fallback path — the
same way the in-memory rate limiter is an accepted, weaker fallback for the
Redis-backed one.
"""

from __future__ import annotations

from typing import Any

from fastapi import BackgroundTasks

from app.core.config import settings
from app.core.email import send_email


async def send_email_task(ctx: dict[str, Any], to: str, subject: str, body_html: str) -> bool:
    """The arq job function — registered in WorkerSettings.functions below.
    `ctx` is arq's job context, unused here but required by arq's calling
    convention for every job function."""
    return await send_email(to=to, subject=subject, body_html=body_html)


async def enqueue_email(
    background_tasks: BackgroundTasks, to: str, subject: str, body_html: str
) -> None:
    """Send an email without blocking the request. Tries arq first if Redis
    is enabled; falls back to BackgroundTasks otherwise — including if Redis
    is enabled but unreachable at the moment of enqueueing, fail open to the
    weaker-but-still-working path rather than losing the email entirely."""
    if settings.REDIS_ENABLED:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            try:
                await pool.enqueue_job("send_email_task", to, subject, body_html)
            finally:
                await pool.aclose()
            return
        except Exception:
            pass  # fall through to BackgroundTasks below

    background_tasks.add_task(send_email, to=to, subject=subject, body_html=body_html)


def _build_worker_settings():
    """Built lazily (called from app/worker.py, not at this module's import
    time) so settings.REDIS_URL is only required to be valid when something
    actually intends to run the worker — importing this module for
    enqueue_email/send_email_task must work even with Redis disabled."""
    from arq.connections import RedisSettings

    class WorkerSettings:
        functions = [send_email_task]
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    return WorkerSettings
