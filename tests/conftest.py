"""
Shared pytest configuration.

Disables automatic `alembic upgrade head` on app startup (see
app.main.lifespan / app.core.config.Settings.RUN_MIGRATIONS_ON_STARTUP)
for the entire test suite — this must happen before app.main (and
therefore app.core.config.settings) is ever imported by any test module,
which is exactly what a conftest.py at the top of the collection is for.

The test suite already has its own fast, correct table-creation
mechanism (test_api.py's `setup_db` fixture calls
`Base.metadata.create_all` directly against an isolated in-memory
SQLite engine, once per test via an autouse fixture) — running a real
`alembic upgrade head` subprocess on top of that, on every single
AsyncClient construction (since the ASGI transport triggers the
FastAPI lifespan each time), is pure redundant work against a database
that's about to be recreated anyway, and a needless source of
environment-dependent flakiness (e.g. if `alembic` isn't on PATH in
some future CI runner shape) for behavior no test here actually
exercises or depends on.
"""

import os

os.environ.setdefault("RUN_MIGRATIONS_ON_STARTUP", "false")
