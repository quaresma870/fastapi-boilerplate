"""
Security utilities — password hashing, JWT token management,
refresh token rotation, and token denylist via Redis.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# ── Password ──────────────────────────────────────────────────────────────────
#
# bcrypt only uses the first 72 BYTES of its input — anything beyond that is
# silently ignored by the algorithm itself. With a raw password handed
# directly to bcrypt, two different passwords sharing the same first 72
# bytes (e.g. "x"*72+"foo" and "x"*72+"bar") hash identically and verify
# against each other, even though the application's own registration schema
# allows passwords up to 128 characters. SHA-256 pre-hashing the password
# before bcrypt collapses it to a fixed 32-byte digest first, so the full
# entropy of an arbitrarily long password is preserved — the same pattern
# Django's bcrypt backend uses. SHA-256's collision resistance is not a
# practical concern at this length.
#
# NOTE — breaking change for any deployment with existing stored hashes:
# this changes what's actually fed into bcrypt, so password hashes created
# before this change will no longer verify. See CHANGELOG.md.

def _prehash(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # malformed/corrupted stored hash — never raise out of a verify call
        return False


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
