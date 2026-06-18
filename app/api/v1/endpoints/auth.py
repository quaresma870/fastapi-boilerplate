"""
Auth endpoints — register, login, refresh (with rotation), logout,
forgot-password, reset-password.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.email import build_reset_email, send_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    deny_token,
    hash_password,
    is_token_denied,
)
from app.schemas.user import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await UserService(db).create(data)


@router.post("/login", response_model=TokenResponse, summary="Login and get tokens")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await UserService(db).authenticate(data.email, data.password)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token (with rotation)",
)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    if await is_token_denied(data.refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked.")

    user = await UserService(db).get_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    await deny_token(data.refresh_token)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout — revokes tokens",
)
async def logout(data: RefreshRequest):
    await deny_token(data.refresh_token)
    return MessageResponse(message="Logged out. Tokens revoked.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset email",
)
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Sends a password reset email if the address exists.
    Always returns 200 to prevent user enumeration.
    """
    user = await UserService(db).get_by_email(data.email)
    if user and user.is_active:
        from datetime import timedelta

        from app.core.security import _create_token

        token = _create_token(user.id, timedelta(hours=1), token_type="password_reset")
        reset_url = f"{settings.ALLOWED_ORIGINS[0]}/reset-password?token={token}"
        background_tasks.add_task(
            send_email,
            to=data.email,
            subject="Password Reset Request",
            body_html=build_reset_email(reset_url),
        )

    return MessageResponse(
        message="If that email exists, a reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a token from email",
)
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(data.token)
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    if await is_token_denied(data.token):
        raise HTTPException(status_code=400, detail="Reset token has already been used.")

    user = await UserService(db).get_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="User not found.")

    # Update password
    user.hashed_password = hash_password(data.new_password)
    await db.flush()

    # Invalidate the reset token so it cannot be reused
    await deny_token(data.token)

    return MessageResponse(message="Password updated successfully. Please log in.")
