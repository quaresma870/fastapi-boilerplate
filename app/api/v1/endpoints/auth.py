"""
Auth endpoints — register, login, refresh, logout.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.schemas.user import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
             summary="Register a new user")
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await UserService(db).create(data)
    return user


@router.post("/login", response_model=TokenResponse, summary="Login and get tokens")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await UserService(db).authenticate(data.email, data.password)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
    user = await UserService(db).get_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (client-side token discard)",
)
async def logout():
    # Stateless JWT: instruct client to discard tokens.
    # To invalidate server-side, add token to a Redis denylist here.
    return MessageResponse(message="Logged out successfully. Discard your tokens.")
