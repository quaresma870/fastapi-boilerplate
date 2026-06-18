"""
Pagination — cursor-based pagination utilities and generic response schema.

Cursor-based is preferred over offset because:
- Consistent results even when rows are inserted/deleted between pages
- O(1) query regardless of page depth
- Safe for large datasets
"""

from __future__ import annotations

import base64
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

_CURSOR_PREFIX = "cursor:"


class Paginated(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    data: list[T]
    next_cursor: str | None = None
    has_more: bool = False


def encode_cursor(last_id: str) -> str:
    raw = f"{_CURSOR_PREFIX}{last_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        if raw.startswith(_CURSOR_PREFIX):
            return raw[len(_CURSOR_PREFIX):]
    except Exception:
        pass
    return None
