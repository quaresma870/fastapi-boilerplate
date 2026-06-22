# ⚡ FastAPI Boilerplate

[![CI](https://github.com/quaresma870/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/quaresma870/fastapi-boilerplate/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi&logoColor=white)
![Node.js](https://img.shields.io/badge/GitHub%20Actions-Node.js%2024-brightgreen?logo=nodedotjs&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

Production-ready FastAPI boilerplate with JWT auth, rate limiting, async SQLAlchemy, Docker, and full CI/CD. Clone and build on top of it.

---

## Features

- ✅ **JWT Auth** — access + refresh tokens (with rotation), bcrypt password hashing (SHA-256 pre-hashed, no 72-byte truncation bug)
- ✅ **Email verification** — sent on registration; account usable immediately, `is_verified` exposed for apps that want to gate on it
- ✅ **Password reset** — forgot/reset flow via single-use, time-limited tokens
- ✅ **Admin user management** — promote/demote, activate/deactivate other users (superuser-gated, self-modification blocked)
- ✅ **Versioned API** — `/api/v1/` prefix, easy to extend to v2
- ✅ **Cursor-based pagination** — `GET /api/v1/users` for admins
- ✅ **Async SQLAlchemy** — SQLite (dev) + PostgreSQL (production), Alembic migrations
- ✅ **Background task queue** — arq (Redis-backed) for outgoing email, falls back to FastAPI `BackgroundTasks` with `REDIS_ENABLED=false`
- ✅ **Rate limiting** — sliding window per IP (Redis-backed, in-memory fallback), stricter on auth endpoints
- ✅ **Production safety guard** — refuses to start with the default `SECRET_KEY` or wildcard `ALLOWED_HOSTS` when `ENVIRONMENT=production`
- ✅ **CORS + Trusted Hosts** middleware
- ✅ **Structured logging** — JSON in production, coloured in development
- ✅ **Prometheus metrics** — `GET /metrics`
- ✅ **Pydantic v2** — request validation, password policy enforcement
- ✅ **Auto docs** — Swagger UI + ReDoc out of the box
- ✅ **Docker Compose** — API + worker + PostgreSQL + Redis in one command; multi-stage, non-root container image
- ✅ **pytest** — 46 tests, in-memory SQLite, no external deps required
- ✅ **GitHub Actions CI** — lint → test → docker build (+ non-root verification) on every push

---

## Quick start

```bash
git clone https://github.com/quaresma870/fastapi-boilerplate.git
cd fastapi-boilerplate
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`
Swagger docs at `http://localhost:8000/api/v1/docs`

### With Docker

```bash
docker compose up --build
```

Starts the API, PostgreSQL, Redis, and a background worker (`worker` service)
that processes queued emails (registration verification, password reset) via
[arq](https://arq-docs.helpmanual.io/). Without Docker, run the worker
separately if you want emails actually delivered asynchronously rather than
falling back to FastAPI's in-process `BackgroundTasks`:

```bash
REDIS_ENABLED=true python -m arq app.worker.WorkerSettings
```

`REDIS_ENABLED=false` (the default) skips the queue entirely and sends email
via `BackgroundTasks` instead — no worker needed, useful for local dev/tests.

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | — | Health check (legacy redirect) |
| GET | `/api/v1/health/live` | — | Liveness probe |
| GET | `/api/v1/health/ready` | — | Readiness probe (DB + Redis) |
| GET | `/metrics` | — | Prometheus metrics |
| POST | `/api/v1/auth/register` | — | Register new user (sends verification email) |
| GET | `/api/v1/auth/verify-email` | — | Verify email from the link sent on registration |
| POST | `/api/v1/auth/login` | — | Login, get tokens |
| POST | `/api/v1/auth/refresh` | — | Refresh access token (with rotation) |
| POST | `/api/v1/auth/logout` | — | Logout, revokes tokens |
| POST | `/api/v1/auth/forgot-password` | — | Request a password reset email |
| POST | `/api/v1/auth/reset-password` | — | Reset password using a token from email |
| GET | `/api/v1/users/me` | Bearer | Get own profile |
| PATCH | `/api/v1/users/me` | Bearer | Update own profile |
| DELETE | `/api/v1/users/me` | Bearer | Delete own account |
| GET | `/api/v1/users` | Superuser | List users (cursor-paginated) |
| GET | `/api/v1/users/{id}` | Superuser | Get any user |
| PATCH | `/api/v1/users/{id}` | Superuser | Activate/deactivate or promote/demote a user |

---

## Project structure

```
fastapi-boilerplate/
├── app/
│   ├── main.py                    # App factory, middleware, router mount
│   ├── api/v1/
│   │   ├── deps.py                # Auth dependencies (get_current_user)
│   │   ├── router.py              # Aggregates all routers
│   │   └── endpoints/
│   │       ├── auth.py            # Register, login, refresh, logout
│   │       └── users.py           # Profile management + admin
│   ├── core/
│   │   ├── config.py              # Settings via pydantic-settings + .env, production safety guard
│   │   ├── database.py            # Async SQLAlchemy engine + session
│   │   ├── security.py            # JWT creation/decoding, bcrypt hashing (SHA-256 pre-hashed)
│   │   ├── email.py               # SMTP sending, degrades gracefully when unconfigured
│   │   ├── tasks.py                # Background task queue — arq, falls back to BackgroundTasks
│   │   ├── rate_limit.py          # Sliding window rate limiter middleware
│   │   └── logging.py             # Structured logging setup
│   ├── worker.py                  # arq worker entry point — python -m arq app.worker.WorkerSettings
│   ├── models/
│   │   └── user.py                # SQLAlchemy User model
│   ├── schemas/
│   │   └── user.py                # Pydantic request/response schemas
│   └── services/
│       └── user.py                # Business logic, decoupled from HTTP
├── tests/
│   └── test_api.py                # 10 integration tests
├── docker/
│   └── Dockerfile
├── docker-compose.yml             # API + PostgreSQL + Redis
├── .github/workflows/ci.yml       # Lint → Test → Docker build
├── .env.example
├── requirements.txt
├── pyproject.toml                 # pytest + ruff config
└── README.md
```

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
# Generate a secure key:
openssl rand -hex 32
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(change me)* | JWT signing key |
| `DATABASE_URL` | SQLite | Switch to PostgreSQL for production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `RATE_LIMIT_PER_MINUTE` | `60` | General rate limit per IP |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `10` | Auth endpoint rate limit per IP |
| `OTEL_ENABLED` | `false` | Turn on distributed tracing (see below) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(empty)* | Where to send traces; empty = print to console |

---

## Tracing

Disabled by default (`OTEL_ENABLED=false`) — the app behaves identically with
it off, no required dependency beyond the already-installed
`opentelemetry-*` packages. Turn it on to see a span per request plus a
nested span per DB query, so you can tell where time in a request actually
went.

With no `OTEL_EXPORTER_OTLP_ENDPOINT` set, spans print to the console — fine
for a quick local look. To view them properly, run a local Jaeger instance:

```yaml
# Add to docker-compose.yml, then set:
#   OTEL_ENABLED=true
#   OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces
  jaeger:
    image: jaegertracing/all-in-one:1.62
    ports:
      - "16686:16686"   # UI at http://localhost:16686
      - "4318:4318"     # OTLP HTTP receiver
```

---

## Running tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database — no setup required.

---

## Extending

This boilerplate is designed to be extended:

- **Add a new resource** — create `models/`, `schemas/`, `services/`, `endpoints/` files and register the router in `api/v1/router.py`
- **Switch to PostgreSQL** — update `DATABASE_URL` in `.env`; run `alembic upgrade head` to apply the existing migrations
- **Enable Redis-backed rate limiting + background email queue** — set `REDIS_ENABLED=true` in `.env` and run the `worker` service (`docker compose up` already includes it)
- **Add a new background task** — register the function in `app/worker.py`'s `WorkerSettings.functions`, following the pattern in `core/tasks.py`'s `send_email_task`
- **Add a new admin-only field** — extend `AdminUserUpdate` in `schemas/user.py` and `UserService.admin_update`, keeping it separate from the self-service `UserUpdate`

---

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## License

MIT
