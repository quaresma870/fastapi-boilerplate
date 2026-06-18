"""
User service — business logic, decoupled from HTTP layer.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        if await self.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )
        if await self.get_by_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This username is already taken.",
            )
        user = User(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is disabled.",
            )
        return user

    async def update(self, user: User, data: UserUpdate) -> User:
        if data.email and data.email != user.email:
            if await self.get_by_email(data.email):
                raise HTTPException(status_code=409, detail="Email already in use.")
            user.email = data.email
        if data.username and data.username != user.username:
            if await self.get_by_username(data.username):
                raise HTTPException(status_code=409, detail="Username already taken.")
            user.username = data.username
        if data.password:
            user.hashed_password = hash_password(data.password)
        await self.db.flush()
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.flush()
