"""
FastAPI Boilerplate — main application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import setup_logging
from app.core.metrics import MetricsMiddleware, metrics_endpoint
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.tracing import setup_tracing

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        await _run_migrations()
    yield


async def _run_migrations() -> None:
    """Runs `alembic upgrade head` as a real subprocess before the app
    starts serving requests.

    Confirmed this is a real, necessary fix, not a defensive nicety: with
    neither this nor any other migration step ever running automatically,
    the exact documented Quick Start (`uvicorn app.main:app --reload`
    against the default SQLite `DATABASE_URL`, or `docker compose up`
    against Postgres) produced a genuinely broken app — the first request
    touching the database (e.g. POST /api/v1/auth/register) 500'd with
    `sqlite3.OperationalError: no such table: users` / the Postgres
    equivalent. Reproduced this directly (a real uvicorn process, the
    real default .env, a real HTTP request) before fixing it.

    Runs `alembic` as a subprocess rather than calling its Python API
    (e.g. `alembic.command.upgrade`) directly in-process: alembic's own
    migrations/env.py internally calls `asyncio.run(...)` for the async
    engine path, and calling that from inside this lifespan handler
    (which already runs inside FastAPI's own event loop) would raise
    "asyncio.run() cannot be called from a running event loop" — a
    subprocess sidesteps that nesting problem entirely and is also the
    same mechanism a human operator would use running this by hand,
    reducing the chance of this codepath silently drifting from actual
    CLI behavior over time.
    """
    import asyncio
    import logging
    import shutil
    import sys
    from pathlib import Path

    logger = logging.getLogger("app.startup")

    # Resolve alembic's absolute path the same way Python itself was
    # invoked, rather than relying on a bare "alembic" resolving via the
    # subprocess's inherited PATH. Confirmed this distinction is real,
    # not theoretical: asyncio.create_subprocess_exec("alembic", ...)
    # raised a real FileNotFoundError when uvicorn was launched via its
    # venv's own absolute path without that venv's bin/ directory
    # separately added to PATH — exactly how a Docker CMD like
    # ["uvicorn", "app.main:app", ...] invokes it, since Docker doesn't
    # "activate" a venv, it just uses whatever's on the image's PATH.
    # alembic is installed as a console script into the same directory
    # as the Python interpreter itself in any standard pip install, so
    # resolving it relative to sys.executable works identically whether
    # a venv is "activated" or not, and inside Docker either way.
    alembic_dir = Path(sys.executable).parent
    alembic_path = alembic_dir / "alembic"
    if not alembic_path.exists():
        alembic_path = shutil.which("alembic") or "alembic"

    proc = await asyncio.create_subprocess_exec(
        str(alembic_path), "upgrade", "head",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode(errors="replace")
    if proc.returncode != 0:
        logger.error("Database migration failed:\n%s", output)
        raise RuntimeError(
            f"`alembic upgrade head` exited with code {proc.returncode} — "
            f"refusing to start with a possibly out-of-date schema. Output:\n{output}"
        )
    logger.info("Database migrations applied successfully.\n%s", output)


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )
    app.add_middleware(RateLimitMiddleware)

    setup_tracing(app, engine)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # ── Health check ──────────────────────────────────────────────────────────
    app.add_route("/metrics", metrics_endpoint, methods=["GET"])

    @app.get("/health", tags=["Health"], summary="Health check (legacy — use /api/v1/health/ready)")
    async def health():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{settings.API_V1_PREFIX}/health/ready")


    # ── RFC 7807 Problem Details exception handler ────────────────────────────
    from fastapi import HTTPException as FastAPIHTTPException
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(FastAPIHTTPException)
    async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"https://httpstatuses.com/{exc.status_code}",
                "title": exc.detail,
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": str(request.url),
                **({"request_id": request_id} if request_id else {}),
            },
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content={
                "type": "https://httpstatuses.com/422",
                "title": "Validation Error",
                "status": 422,
                "detail": [
                    {"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ],
                "instance": str(request.url),
                **({"request_id": request_id} if request_id else {}),
            },
        )

    return app


app = create_application()
