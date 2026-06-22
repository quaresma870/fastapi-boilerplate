"""
Application configuration — loaded from environment variables / .env file.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET_KEY = "change-me-in-production-use-openssl-rand-hex-32"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # ── Project ───────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "FastAPI Boilerplate"
    PROJECT_DESCRIPTION: str = (
        "Production-ready FastAPI boilerplate with JWT auth, "
        "rate limiting, versioned API, and full CI-CD."
    )
    VERSION: str = "1.0.5"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # ── API ───────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = _INSECURE_DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"
    # For PostgreSQL: postgresql+asyncpg://user:password@host:5432/dbname

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False  # set True when Redis is available

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60          # per IP, general endpoints
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10     # per IP, auth endpoints

    # ── Tracing (optional — see core/tracing.py) ──────────────────────────────
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "fastapi-boilerplate"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""    # e.g. http://localhost:4318/v1/traces
                                              # empty = export to console instead

    # ── CORS / Hosts ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    ALLOWED_HOSTS: list[str] = ["*"]

    # ── Email (optional) ──────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM: str = "noreply@example.com"

    @model_validator(mode="after")
    def _refuse_insecure_production_defaults(self) -> "Settings":
        """Fail fast and loud at startup rather than silently running an
        insecure configuration. SECRET_KEY's default is a known public
        string (it's right there in this repo's source on GitHub) — any
        production deployment that didn't override it would let anyone
        forge valid JWTs, including ones claiming superuser access.
        ALLOWED_HOSTS=["*"] disables Host-header validation entirely.
        Both are reasonable, convenient defaults for local development,
        which is exactly why they must be checked before anything is
        actually exposed as 'production'.
        """
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == _INSECURE_DEFAULT_SECRET_KEY:
                raise ValueError(
                    "Refusing to start: ENVIRONMENT=production but SECRET_KEY is still "
                    "the insecure default. Set a real secret, e.g.: "
                    "SECRET_KEY=$(openssl rand -hex 32)"
                )
            if self.ALLOWED_HOSTS == ["*"]:
                raise ValueError(
                    "Refusing to start: ENVIRONMENT=production but ALLOWED_HOSTS is still "
                    "the wildcard default. Set it to your actual domain(s), e.g.: "
                    'ALLOWED_HOSTS=["api.example.com"]'
                )
        return self


settings = Settings()
