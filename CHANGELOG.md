# Changelog

All notable changes to this project are documented here. See the
[README](README.md) for current features and usage.

### v1.0.4
- feat: cursor-based pagination on `GET /api/v1/users` — closes #12
  (`?limit=20&cursor=<token>`, response: `{data, next_cursor, has_more, total}`)
- feat: password reset flow — closes #13
  (`POST /auth/forgot-password` → email → `POST /auth/reset-password`, token single-use)
- feat: `GET /metrics` Prometheus endpoint — closes #14
  (`http_requests_total`, `http_request_duration_seconds` with path normalisation)
- chore: dependency updates from Dependabot — closes #7 #8 #9 #10 #11
  - `sqlalchemy` ≥2.0.51
  - `asyncpg` ≥0.31.0
  - `pydantic-settings` ≥2.14.1
  - `pytest-asyncio` ≥1.4.0
  - `ruff` ≥0.8.0
  - `redis[asyncio]` extra removed (bundled in redis ≥5.0)

### v1.0.3
- feat: Redis-backed rate limiter with in-memory fallback — closes #2
  (`X-RateLimit-Backend: redis|memory` header indicates active backend)
- feat: refresh token rotation — closes #3
  (used refresh tokens are invalidated; logout adds token to Redis denylist)
- feat: RFC 7807 Problem Details error responses + `X-Request-ID` middleware — closes #5
- feat: Alembic migrations configured for async SQLAlchemy — closes #1
  (initial migration generated; run `alembic upgrade head` to apply)

### v1.0.2
- feat: `/api/v1/health/live` — liveness probe (process alive check)
- feat: `/api/v1/health/ready` — readiness probe with real DB + Redis connectivity checks — closes #4
- fix: `/health` redirects to `/api/v1/health/ready` for backwards compatibility
- chore: Dependabot enabled for pip and GitHub Actions (weekly) — closes #6

### v1.0.1
- fix: `DATABASE_URL` value quoted in CI workflow — trailing colon broke YAML parser
- fix: all 21 ruff lint errors resolved (import sorting, deprecated `Optional`/`List`/`Dict` type hints, line length)
- fix: `pyproject.toml` ruff config moved to `[tool.ruff.lint]` section
- chore: `bcrypt` pinned to `4.0.1` in `requirements.txt` for `passlib` compatibility
- chore: all GitHub Actions upgraded to Node.js 24 runtime (`checkout@v6`, `setup-python@v6`, `setup-buildx-action@v4`, `build-push-action@v7`)
