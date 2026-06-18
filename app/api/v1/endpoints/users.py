"""
Users endpoints — profile management and admin operations.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_superuser, get_current_user
from app.core.database import get_db
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

@router.get("/{user_id}", response_model=UserResponse,
            summary="[Admin] Get any user by ID",
            dependencies=[Depends(get_current_superuser)])
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    user = await UserService(db).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user
