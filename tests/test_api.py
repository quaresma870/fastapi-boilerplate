"""
Integration tests — auth and user endpoints.
Uses an in-memory SQLite database, no external services required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Clear rate limiter state between tests
    from app.core.rate_limit import _store
    _store._windows.clear()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async def override_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def register_user(client, email="user@test.com", username="testuser", password="Secure123"):
    return await client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "password": password
    })


async def login_user(client, email="user@test.com", password="Secure123"):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Register ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client):
    r = await register_user(client)
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "user@test.com"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await register_user(client)
    r = await register_user(client)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client):
    r = await register_user(client, password="weakpass")
    assert r.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client):
    await register_user(client)
    r = await login_user(client)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await register_user(client)
    r = await login_user(client, password="WrongPass1")
    assert r.status_code == 401


# ── Token refresh ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token(client):
    await register_user(client)
    login_r = await login_user(client)
    assert login_r.status_code == 200
    tokens = login_r.json()
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


# ── Protected routes ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me(client):
    await register_user(client)
    login_r = await login_user(client)
    assert login_r.status_code == 200
    tokens = login_r.json()
    r = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "user@test.com"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client):
    r = await client.get("/api/v1/users/me")
    assert r.status_code in (401, 403)  # HTTPBearer returns 403 when no token present


@pytest.mark.asyncio
async def test_delete_me(client):
    await register_user(client)
    login_r = await login_user(client)
    assert login_r.status_code == 200
    tokens = login_r.json()
    r = await client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert r.status_code == 200
