"""Pytest configuration and fixtures."""
import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

os.environ.setdefault("APP_ENV", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.models import Membership, Tenant, User
from app.db.workflow_models import Base as WorkflowBase
from app.db.models import Base as AuthBase
from app.core.security import hash_password
from app.db.session import get_db_session
from app.main import app


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"




@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(AuthBase.metadata.create_all)
        await conn.run_sync(WorkflowBase.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(WorkflowBase.metadata.drop_all)
        await conn.run_sync(AuthBase.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """Create a test database session."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Tenant",
        slug="test-tenant",
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a test user with membership."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        full_name="Test User",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=test_tenant.id,
        role="admin",
    )
    db_session.add(membership)
    await db_session.commit()
    
    return user


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Create an API client backed by the test database session."""

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(test_user: User, test_tenant: Tenant) -> dict[str, str]:
    """Create bearer auth headers for the test user and tenant."""
    token = create_access_token(subject=str(test_user.id), tenant_id=str(test_tenant.id))
    return {"Authorization": f"Bearer {token}"}
