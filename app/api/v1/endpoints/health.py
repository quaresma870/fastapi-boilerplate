"""
Health check endpoints — liveness and readiness probes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health/live", summary="Liveness probe — is the process alive?")
async def liveness():
    """Always returns 200 if the process is running."""
    return {"status": "ok", "version": settings.VERSION}


@router.get("/health/ready", summary="Readiness probe — are dependencies healthy?")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Returns 200 only if DB (and Redis if enabled) are reachable."""
    checks: dict[str, str] = {}
    overall_ok = True

    # ── Database check ────────────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        overall_ok = False

    # ── Redis check (optional) ────────────────────────────────────────────────
    if settings.REDIS_ENABLED:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"
            overall_ok = False
    else:
        checks["redis"] = "disabled"

    status_code = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if overall_ok else "degraded",
            "version": settings.VERSION,
            "checks": checks,
        },
    )
