# ⚡ FastAPI Boilerplate

[![CI](https://github.com/quaresma870/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/quaresma870/fastapi-boilerplate/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi&logoColor=white)
![Node.js](https://img.shields.io/badge/GitHub%20Actions-Node.js%2024-brightgreen?logo=nodedotjs&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

Production-ready FastAPI boilerplate with JWT auth, rate limiting, async SQLAlchemy, Docker, and full CI/CD. Clone and build on top of it.

---

## Features

- ✅ **JWT Auth** — access + refresh tokens, bcrypt password hashing
- ✅ **Versioned API** — `/api/v1/` prefix, easy to extend to v2
- ✅ **Async SQLAlchemy** — SQLite (dev) + PostgreSQL (production)
- ✅ **Rate limiting** — sliding window per IP, stricter on auth endpoints
- ✅ **CORS + Trusted Hosts** middleware
- ✅ **Structured logging** — JSON in production, coloured in development
- ✅ **Pydantic v2** — request validation, password policy enforcement
- ✅ **Auto docs** — Swagger UI + ReDoc out of the box
- ✅ **Docker Compose** — API + PostgreSQL + Redis in one command
- ✅ **pytest** — 10 integration tests, in-memory SQLite, no external deps
- ✅ **GitHub Actions CI** — lint → test → docker build on every push

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

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | — | Health check (legacy redirect) |
| GET | `/api/v1/health/live` | — | Liveness probe |
| GET | `/api/v1/health/ready` | — | Readiness probe (DB + Redis) |
| POST | `/api/v1/auth/register` | — | Register new user |
| POST | `/api/v1/auth/login` | — | Login, get tokens |
| POST | `/api/v1/auth/refresh` | — | Refresh access token |
| POST | `/api/v1/auth/logout` | — | Logout |
| GET | `/api/v1/users/me` | Bearer | Get own profile |
| PATCH | `/api/v1/users/me` | Bearer | Update own profile |
| DELETE | `/api/v1/users/me` | Bearer | Delete own account |
| GET | `/api/v1/users/{id}` | Superuser | Get any user |

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
│   │   ├── config.py              # Settings via pydantic-settings + .env
│   │   ├── database.py            # Async SQLAlchemy engine + session
│   │   ├── security.py            # JWT creation/decoding, bcrypt hashing
│   │   ├── rate_limit.py          # Sliding window rate limiter middleware
│   │   └── logging.py             # Structured logging setup
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

---

## Running tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database — no setup required.

---

## Changelog

### v1.0.1
- fix: `DATABASE_URL` value quoted in CI workflow — trailing colon broke YAML parser
- fix: all 21 ruff lint errors resolved (import sorting, deprecated `Optional`/`List`/`Dict` type hints, line length)
- fix: `pyproject.toml` ruff config moved to `[tool.ruff.lint]` section
- chore: `bcrypt` pinned to `4.0.1` in `requirements.txt` for `passlib` compatibility
- chore: all GitHub Actions upgraded to Node.js 24 runtime (`checkout@v6`, `setup-python@v6`, `setup-buildx-action@v4`, `build-push-action@v7`)

---

## Extending

This boilerplate is designed to be extended:

- **Add a new resource** — create `models/`, `schemas/`, `services/`, `endpoints/` files and register the router in `api/v1/router.py`
- **Switch to PostgreSQL** — update `DATABASE_URL` in `.env`; run `alembic init` for migrations
- **Enable Redis rate limiting** — set `REDIS_ENABLED=true` in `.env` (Redis backend coming soon)
- **Add email verification** — wire up `SMTP_*` settings in `.env` and call from the register endpoint

---

## Changelog

### v1.0.2
- feat: `/api/v1/health/live` — liveness probe (process alive check)
- feat: `/api/v1/health/ready` — readiness probe with real DB + Redis connectivity checks — closes #4
- fix: `/health` redirects to `/api/v1/health/ready` for backwards compatibility
- chore: Dependabot enabled for pip and GitHub Actions (weekly) — closes #6

---

## License

MIT
