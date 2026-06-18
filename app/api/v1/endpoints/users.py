"""
Users endpoints — profile management, admin operations, and paginated listing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_superuser, get_current_user
from app.core.database import get_db
from app.core.pagination import PaginatedResponse, decode_cursor, encode_cursor
from app.models.user import User
from app.schemas.user import MessageResponse, UserResponse, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse, summary="Update current user profile")
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await UserService(db).update(current_user, data)


@router.delete("/me", response_model=MessageResponse, summary="Delete current user account")
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await UserService(db).delete(current_user)
    return MessageResponse(message="Account deleted successfully.")


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="[Admin] List users with cursor-based pagination",
    dependencies=[Depends(get_current_superuser)],
)
async def list_users(
    limit: int = Query(default=20, ge=1, le=100, description="Number of results per page"),
    cursor: str | None = Query(default=None, description="Opaque cursor from previous page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a paginated list of users.

    - Use `next_cursor` from the response as the `cursor` param for the next page.
    - `has_more: false` means you're on the last page.
    """
    # Decode cursor → last seen ID
    after_id: str | None = None
    if cursor:
        after_id = decode_cursor(cursor)
        if after_id is None:
            raise HTTPException(status_code=400, detail="Invalid cursor.")

    # Build query
    query = select(User).order_by(User.id)
    if after_id:
        query = query.where(User.id > after_id)

    # Fetch limit + 1 to detect has_more
    query = query.limit(limit + 1)
    result = await db.execute(query)
    rows = result.scalars().all()

    has_more = len(rows) > limit
    page = rows[:limit]

    next_cursor = encode_cursor(page[-1].id) if has_more and page else None

    # Total count (optional — can be expensive on large tables)
    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar_one()

    return PaginatedResponse(
        data=page,
        next_cursor=next_cursor,
        has_more=has_more,
        total=total,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="[Admin] Get any user by ID",
    dependencies=[Depends(get_current_superuser)],
)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await UserService(db).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user
