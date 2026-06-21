# Changelog

All notable changes to this project are documented here. See the
[README](README.md) for current features and usage.

### v1.0.5
- fix: **silent password truncation past 72 bytes** — passwords were hashed by handing them
  directly to bcrypt via `passlib`, but bcrypt only ever uses the first 72 bytes of its input.
  Two different passwords sharing the same first 72 bytes (e.g. `"x"*72+"foo"` vs `"x"*72+"bar"`)
  hashed identically and verified against each other, even though the registration schema
  explicitly allows passwords up to 128 characters — demonstrated and confirmed before fixing,
  not assumed. Fixed by SHA-256 pre-hashing the password before bcrypt (the same pattern Django's
  bcrypt backend uses), which collapses any input to a fixed 32-byte digest first, preserving the
  full entropy of arbitrarily long passwords. **Breaking change for any deployment with existing
  stored hashes** — they were computed over the raw password, not the new pre-hashed digest, and
  will no longer verify. Force a password reset for existing users after upgrading, or implement
  dual verification (try new scheme, fall back to old, re-hash on successful legacy login) if
  upgrading a deployment with real user data.
- chore: replaced `passlib` (unmaintained, last released years ago, known incompatibility with
  newer `bcrypt` releases — this project had `bcrypt` pinned to `4.0.1` specifically to work
  around it) with a small direct wrapper around the `bcrypt` library. Also removes the
  `DeprecationWarning` passlib triggered via its `crypt`-module probing, which would have become a
  hard failure once Python 3.13 actually removes that module. `bcrypt` is now unpinned
  (`>=4.1.0`).
- fix: `Settings` now refuses to start when `ENVIRONMENT=production` and either `SECRET_KEY` is
  still its known-public default value (published right here in this repo's source — any
  deployment that didn't override it would let anyone forge valid JWTs, including ones claiming
  superuser access) or `ALLOWED_HOSTS` is still the wildcard default (disables Host-header
  validation entirely). Fails fast and loud at config-load time with an actionable error message,
  rather than silently running insecurely. Scoped to `production` only — `development`/`staging`
  keep working with the convenient defaults.
- fix: `settings.VERSION` (served in `/health` and the OpenAPI docs) was still `"1.0.0"` through
  four real releases — bumped to match, plus a regression test that checks `settings.VERSION`
  against `CHANGELOG.md`'s latest entry going forward.
- chore: removed leftover empty junk directories from an early shell command that didn't expand
  brace patterns as intended (`{api/v1/endpoints,core,...}` etc.) — never tracked in git, purely
  local clutter, but worth a clean sweep.

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
