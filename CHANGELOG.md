# Changelog

All notable changes to this project are documented here. See the
[README](README.md) for current features and usage.

### v1.1.0
- feat: **Docker hardening** — multi-stage build (no compiler/build toolchain shipped in the
  runtime image) and a non-root `app` user. CI's docker build job extended to also load the
  built image and verify `docker run ... whoami` isn't root, not just that it builds.
- feat: **admin user management** — `PATCH /users/{user_id}` lets a superuser activate/deactivate
  or promote/demote another user. While scoping this, found that the core admin/superuser gate
  (`get_current_superuser`, plus two already-gated endpoints) already existed and was already
  tested — re-scoped to the genuine remaining gap: admins could view other users but had no way to
  manage them without direct DB access. Refuses to target the caller's own account, so a superuser
  can't accidentally demote or deactivate themselves.
- feat: **email verification on registration** — `User.is_verified` (new column + migration),
  sent via a single-use 24h token on `POST /auth/register`, confirmed via
  `GET /auth/verify-email`. Registration and login are explicitly *not* blocked on verification
  (documented policy decision, not left implicit) — `is_verified` is exposed for any consuming app
  that wants to gate specific actions on it more strictly.
- feat: **background task queue (arq)** for outgoing email — `core/tasks.enqueue_email()` uses
  arq (Redis-backed) when `REDIS_ENABLED=true`, falling back to FastAPI's `BackgroundTasks`
  otherwise, including if Redis is enabled but unreachable at enqueue time. Migrated both existing
  email call sites (verification, password reset) to this single mechanism rather than leaving two
  different background-execution paths for the same kind of operation. New `worker` service in
  `docker-compose.yml`; run bare with `python -m arq app.worker.WorkerSettings`.
- feat: **distributed tracing (OpenTelemetry)** — `core/tracing.setup_tracing()`, gated by
  `OTEL_ENABLED` (same optional-dependency pattern as Redis elsewhere in this project).
  Instruments FastAPI request handling and SQLAlchemy queries; exports via OTLP/HTTP when
  configured, otherwise prints spans to the console with zero extra infrastructure required.
  README includes a docker-compose Jaeger snippet for actually viewing traces locally.
- docs: refreshed several already-stale README sections found while documenting the above — the
  "Extending" section told people to run `alembic init` as if migrations weren't already set up
  (they have been for a while), and listed Redis-backed rate limiting as "coming soon" when it had
  already shipped. The API endpoints table was missing `verify-email`, `forgot/reset-password`,
  `/metrics`, and the admin list/update-user endpoints entirely.
- test: 18 new tests across the five features above (admin user management, email verification,
  the task queue's fallback/arq paths, and tracing's disabled/enabled behaviour including a real
  DB-spanning trace captured via `InMemorySpanExporter`) — 31 → 49 total.

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
