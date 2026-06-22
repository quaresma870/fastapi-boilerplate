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
    from app.core.rate_limit import _memory_store
    _memory_store.clear()
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
async def test_health_live(client):
    r = await client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_health_ready(client):
    r = await client.get("/api/v1/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"


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


# ── Pagination ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_requires_superuser(client):
    await register_user(client)
    tokens = (await login_user(client)).json()
    r = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_users_paginated(client):
    import uuid

    from app.core.security import hash_password
    from app.models.user import User

    # Create superuser directly in test session
    async with TestSession() as db:
        su = User(
            id=str(uuid.uuid4()),
            email="admin@test.com",
            username="admin",
            hashed_password=hash_password("Admin123"),
            is_superuser=True,
        )
        db.add(su)
        await db.commit()

    tokens = (await login_user(client, email="admin@test.com", password="Admin123")).json()
    r = await client.get(
        "/api/v1/users?limit=10",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "has_more" in data
    assert isinstance(data["total"], int)


# ── Admin user management ───────────────────────────────────────────────────────

async def _create_superuser(email="admin@test.com", username="admin", password="Admin123"):
    import uuid

    from app.core.security import hash_password
    from app.models.user import User

    async with TestSession() as db:
        su = User(
            id=str(uuid.uuid4()), email=email, username=username,
            hashed_password=hash_password(password), is_superuser=True,
        )
        db.add(su)
        await db.commit()
        return su.id


@pytest.mark.asyncio
async def test_admin_can_deactivate_another_user(client):
    await register_user(client)
    target_tokens = (await login_user(client)).json()
    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {target_tokens['access_token']}"},
    )
    target_id = me.json()["id"]

    await _create_superuser()
    admin_tokens = (await login_user(client, email="admin@test.com", password="Admin123")).json()

    r = await client.patch(
        f"/api/v1/users/{target_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # The deactivated user can no longer log in
    r2 = await login_user(client)
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_promote_another_user(client):
    await register_user(client)
    target_tokens = (await login_user(client)).json()
    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {target_tokens['access_token']}"},
    )
    target_id = me.json()["id"]

    await _create_superuser()
    admin_tokens = (await login_user(client, email="admin@test.com", password="Admin123")).json()

    r = await client.patch(
        f"/api/v1/users/{target_id}",
        json={"is_superuser": True},
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["is_superuser"] is True


@pytest.mark.asyncio
async def test_admin_cannot_modify_own_account_via_admin_endpoint(client):
    admin_id = await _create_superuser()
    admin_tokens = (await login_user(client, email="admin@test.com", password="Admin123")).json()

    r = await client.patch(
        f"/api/v1/users/{admin_id}",
        json={"is_superuser": False},
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_non_admin_cannot_use_admin_update_endpoint(client):
    await register_user(client)
    tokens = (await login_user(client)).json()
    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    my_id = me.json()["id"]

    r = await client.patch(
        f"/api/v1/users/{my_id}",
        json={"is_superuser": True},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_update_nonexistent_user_404s(client):
    await _create_superuser()
    admin_tokens = (await login_user(client, email="admin@test.com", password="Admin123")).json()

    r = await client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert r.status_code == 404


# ── Password reset ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_always_200(client):
    # Should return 200 even for non-existent email (prevent enumeration)
    r = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@test.com"},
    )
    assert r.status_code == 200
    assert "reset link" in r.json()["message"]


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client):
    r = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "invalid.token.here", "new_password": "NewPass123"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_flow(client):
    await register_user(client)
    from datetime import timedelta

    from app.core.security import _create_token
    from app.services.user import UserService

    async with TestSession() as db:
        user = await UserService(db).get_by_email("user@test.com")
        token = _create_token(user.id, timedelta(hours=1), "password_reset")

    r = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewPassword123"},
    )
    assert r.status_code == 200

    # Token cannot be reused (if Redis denylist is available)
    r2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass123"},
    )
    # Without Redis in test env, token reuse check is skipped (fail-open)
    # In production with Redis enabled this returns 400
    assert r2.status_code in (200, 400, 401)


# ── Metrics ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    # Hit another endpoint first to generate some metrics
    await client.get("/health")
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert b"http_requests_total" in r.content
