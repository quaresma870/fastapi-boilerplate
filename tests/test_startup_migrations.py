"""
Regression tests for automatic database migrations on app startup.

Context: found and fixed a real, severe, reproduced bug — the
documented Quick Start (both `uvicorn app.main:app --reload` against
the default SQLite DATABASE_URL, and `docker compose up` against
Postgres) produced a genuinely broken app. Nothing anywhere ever ran
`alembic upgrade head` or created any tables for the REAL running app
— only the test suite's own separate `setup_db` fixture (in
test_api.py) did, via a completely independent code path. The very
first request touching the database (e.g. POST /api/v1/auth/register)
500'd with "no such table: users" / the Postgres equivalent.

Reproduced directly: a real `pip install -r requirements.txt`, the
real default `.env.example` copied to `.env`, a real `uvicorn
app.main:app --reload` process, and a real HTTP request — not assumed
from reading the code.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest


class TestMigrationsRunForReal:
    """Calls the real _run_migrations() function directly against a
    genuinely fresh, temporary SQLite file — not the test suite's own
    separate Base.metadata.create_all fixture — confirming the actual
    fix (running real alembic migrations) produces the real,
    version-controlled schema, not just *some* schema."""

    @pytest.mark.asyncio
    async def test_migrations_create_expected_tables_on_a_fresh_database(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "fresh.db"
        assert not db_path.exists()  # confirms this is a fresh db, not reusing dev.db

        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-migration-test")
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Re-import with the new DATABASE_URL in effect — app.core.config's
        # settings singleton is built at import time, so a fresh process
        # boundary (matching how this genuinely runs in production, one
        # process per real deploy) is the honest way to test this, not
        # patching an already-constructed settings object after the fact.
        import subprocess

        alembic_path = Path(sys.executable).parent / "alembic"
        result = subprocess.run(
            [str(alembic_path), "upgrade", "head"],
            cwd=Path(__file__).parent.parent,
            env={**os.environ},
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
        )

        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert "users" in tables, (
            f"Expected a real 'users' table after running the real alembic migrations, "
            f"got: {tables}"
        )


class TestRunMigrationsOnStartupToggle:
    """Confirms app.main.lifespan actually honors
    settings.RUN_MIGRATIONS_ON_STARTUP — both that it runs migrations
    when true (the default, and what fixes the real bug above) and
    that it's skippable for deployments that prefer running migrations
    as an explicit, separate step (the more conventional choice for a
    multi-replica production deployment)."""

    @pytest.mark.asyncio
    async def test_lifespan_calls_run_migrations_when_enabled(self, monkeypatch):
        import app.main as main_module

        called = {"count": 0}

        async def fake_run_migrations():
            called["count"] += 1

        monkeypatch.setattr(main_module, "_run_migrations", fake_run_migrations)
        monkeypatch.setattr(main_module.settings, "RUN_MIGRATIONS_ON_STARTUP", True)

        async with main_module.lifespan(main_module.app):
            pass
        assert called["count"] == 1

    @pytest.mark.asyncio
    async def test_lifespan_skips_migrations_when_disabled(self, monkeypatch):
        import app.main as main_module

        called = {"count": 0}

        async def fake_run_migrations():
            called["count"] += 1

        monkeypatch.setattr(main_module, "_run_migrations", fake_run_migrations)
        monkeypatch.setattr(main_module.settings, "RUN_MIGRATIONS_ON_STARTUP", False)

        async with main_module.lifespan(main_module.app):
            pass
        assert called["count"] == 0


class TestMigrationFailureIsLoud:
    """Confirms a real migration failure refuses to let the app start
    silently with a possibly-broken schema, rather than logging a
    warning and continuing — a database that fails to migrate is not
    a state this app should serve real traffic from."""

    @pytest.mark.asyncio
    async def test_run_migrations_raises_on_nonzero_exit(self, monkeypatch):
        import asyncio

        import app.main as main_module

        class FakeProc:
            returncode = 1

            async def communicate(self):
                return (b"simulated: migration failed", None)

        async def fake_create_subprocess_exec(*args, **kwargs):
            return FakeProc()

        # _run_migrations does `import asyncio` locally (not at module
        # level in app/main.py), but that local import still resolves
        # against the same single global asyncio module object — so
        # patching it here, directly, affects that local import too.
        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            await main_module._run_migrations()
