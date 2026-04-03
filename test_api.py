"""
Test suite for PHR System API.
Run: pytest tests/ -v --cov=app
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.database import Base, get_db


# ── Test Database ─────────────────────────────────────────────────────────────

TEST_DB_URL = "postgresql+asyncpg://phr_user:phr_password@localhost:5432/phr_test"

test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Auth Tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_patient(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "patient@test.com",
        "password": "TestPass123",
        "full_name": "Test Patient",
        "role": "patient",
        "phone": "+919876543210",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "patient@test.com"
    assert data["role"] == "patient"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "dupe@test.com",
        "password": "TestPass123",
        "full_name": "Dupe User",
        "role": "patient",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/v1/auth/register", json={
        "email": "login@test.com",
        "password": "TestPass123",
        "full_name": "Login User",
        "role": "patient",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "login@test.com",
        "password": "TestPass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "patient"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "wrongpass@test.com",
        "password": "TestPass123",
        "full_name": "WP User",
        "role": "patient",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrongpass@test.com",
        "password": "WrongPassword999",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    await client.post("/api/v1/auth/register", json={
        "email": "me@test.com",
        "password": "TestPass123",
        "full_name": "Me User",
        "role": "patient",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "me@test.com",
        "password": "TestPass123",
    })
    token = login.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@test.com"


# ── Patient Profile Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_patient_profile(client):
    await client.post("/api/v1/auth/register", json={
        "email": "profile@test.com",
        "password": "TestPass123",
        "full_name": "Profile User",
        "role": "patient",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "profile@test.com",
        "password": "TestPass123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put("/api/v1/patients/me", headers=headers, json={
        "blood_group": "O+",
        "height_cm": 175.0,
        "weight_kg": 70.0,
        "allergies": ["penicillin", "pollen"],
        "city": "Mumbai",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["blood_group"] == "O+"
    assert data["height_cm"] == 175.0
    assert "penicillin" in data["allergies"]


# ── Vital Signs Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_list_vitals(client):
    await client.post("/api/v1/auth/register", json={
        "email": "vitals@test.com",
        "password": "TestPass123",
        "full_name": "Vitals User",
        "role": "patient",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "vitals@test.com",
        "password": "TestPass123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    vital_payload = {
        "recorded_at": "2024-06-15T09:00:00Z",
        "heart_rate": 72.0,
        "systolic_bp": 118.0,
        "diastolic_bp": 76.0,
        "oxygen_saturation": 98.0,
        "temperature": 36.8,
        "source": "manual",
    }
    add_resp = await client.post("/api/v1/patients/me/vitals", headers=headers, json=vital_payload)
    assert add_resp.status_code == 201

    list_resp = await client.get("/api/v1/patients/me/vitals", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1


# ── Health Check ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
