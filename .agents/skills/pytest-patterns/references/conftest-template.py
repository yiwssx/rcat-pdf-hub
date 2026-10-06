"""
conftest-template.py — Production-grade root conftest for FastAPI + SQLAlchemy async tests.

Place this file at: tests/conftest.py

Provides:
  - Async SQLAlchemy engine and session fixtures (SQLite in-memory for speed)
  - httpx.AsyncClient fixture wired to the FastAPI app with DB override
  - Authentication helper fixtures (standard user, admin user)
  - Factory session wiring

Dependencies:
  pip install pytest pytest-asyncio httpx sqlalchemy[asyncio] aiosqlite factory-boy
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.main import app
from app.database import Base, get_db
from app.auth import create_access_token


# ─── Engine & Session ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    """Select asyncio as the async backend for the entire test session."""
    return "asyncio"


@pytest.fixture(scope="session")
async def engine():
    """Create an async engine and initialize all tables once per session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    """
    Provide a transactional database session that rolls back after each test.

    This ensures complete test isolation -- each test starts with a clean state.
    """
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        async with session.begin():
            yield session
            # Rollback any changes made during the test
            await session.rollback()


# ─── HTTP Client ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def client(db_session: AsyncSession):
    """
    Async HTTP client pointing at the FastAPI app.

    The app's database dependency is overridden to use the test session,
    so all requests share the same transactional session (and its rollback).
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ─── Authentication Helpers ──────────────────────────────────────────────────────

def _make_auth_headers(user_id: int, role: str = "member") -> dict[str, str]:
    """Create Authorization headers with a JWT for the given user."""
    token = create_access_token(data={"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Authorization headers for a standard test user (id=1, role=member)."""
    return _make_auth_headers(user_id=1, role="member")


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Authorization headers for an admin user (id=99, role=admin)."""
    return _make_auth_headers(user_id=99, role="admin")


@pytest.fixture
async def authenticated_client(client: AsyncClient, auth_headers: dict) -> AsyncClient:
    """AsyncClient pre-configured with standard user auth headers."""
    client.headers.update(auth_headers)
    return client


@pytest.fixture
async def admin_client(client: AsyncClient, admin_headers: dict) -> AsyncClient:
    """AsyncClient pre-configured with admin auth headers."""
    client.headers.update(admin_headers)
    return client


# ─── Factory Session Wiring ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _wire_factories(db_session: AsyncSession):
    """
    Automatically set the DB session on all SQLAlchemy-backed factories.

    Import your factories here so they use the per-test transactional session.
    """
    from tests.factories.user_factory import UserFactory
    from tests.factories.order_factory import OrderFactory

    UserFactory._meta.sqlalchemy_session = db_session
    OrderFactory._meta.sqlalchemy_session = db_session


# ─── Sample Data Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
async def sample_user(db_session: AsyncSession):
    """Create and persist a standard user for tests that need an existing user."""
    from tests.factories.user_factory import UserFactory

    user = UserFactory()
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def sample_order(db_session: AsyncSession, sample_user):
    """Create and persist an order linked to the sample_user."""
    from tests.factories.order_factory import OrderFactory

    order = OrderFactory(user_id=sample_user.id)
    db_session.add(order)
    await db_session.flush()
    return order
