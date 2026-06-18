"""
Application configuration — loaded from environment variables / .env file.
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # ── API ───────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
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

    # ── CORS / Hosts ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # ── Email (optional) ──────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM: str = "noreply@example.com"


settings = Settings()
