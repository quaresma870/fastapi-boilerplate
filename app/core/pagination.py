"""
Pagination — cursor-based pagination utilities.

Uses opaque base64-encoded cursors (wrapping the last seen ID)
to avoid the drift issues of offset-based pagination.
"""

from __future__ import annotations

import base64
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

_PREFIX = "cursor:"


def encode_cursor(value: str) -> str:
    """Encode a value into an opaque cursor string."""
    return base64.urlsafe_b64encode(f"{_PREFIX}{value}".encode()).decode()


def decode_cursor(cursor: str) -> str | None:
    """Decode a cursor string. Returns None if invalid."""
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        if decoded.startswith(_PREFIX):
            return decoded[len(_PREFIX):]
    except Exception:
        pass
    return None


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope."""

    data: list[T]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None
