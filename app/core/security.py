"""
Security utilities — password hashing, JWT token management,
refresh token rotation, and token denylist via Redis.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Tokens ────────────────────────────────────────────────────────────────────

def _create_token(subject: Any, expires_delta: timedelta, token_type: str) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": token_type,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: Any) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )


def create_refresh_token(subject: Any) -> str:
    return _create_token(
        subject,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns payload or None on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── Token denylist (Redis) ────────────────────────────────────────────────────

_DENYLIST_PREFIX = "denylist:"


async def _get_redis():
    """Return async Redis client if available, else None."""
    if not settings.REDIS_ENABLED:
        return None
    try:
        import redis.asyncio as aioredis
        return aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
        )
    except Exception:
        return None


async def deny_token(token: str) -> None:
    """Add a token to the denylist. TTL matches token expiry."""
    payload = decode_token(token)
    if not payload:
        return
    exp = payload.get("exp")
    if not exp:
        return
    ttl = int(exp - datetime.now(timezone.utc).timestamp())
    if ttl <= 0:
        return  # already expired
    r = await _get_redis()
    if r:
        try:
            await r.setex(f"{_DENYLIST_PREFIX}{token}", ttl, "1")
        finally:
            await r.aclose()


async def is_token_denied(token: str) -> bool:
    """Return True if token has been revoked."""
    r = await _get_redis()
    if not r:
        return False  # no Redis — can't check denylist, fail open
    try:
        result = await r.exists(f"{_DENYLIST_PREFIX}{token}")
        return bool(result)
    except Exception:
        return False
    finally:
        await r.aclose()
