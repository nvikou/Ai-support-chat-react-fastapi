"""Shared test fixtures; env must exist before app imports Settings.

All fixtures are offline: SQLite (StaticPool), FakeRedis, and doubles
for the LLM / vector store. No OpenAI key, Docker, or network required.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import fakeredis
import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Environment — must run before ``app.*`` imports pull Settings.
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-at-least-32-characters-long",
)
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("GROUNDEDNESS_ENABLED", "false")

from app.agent_access import override_agent  # noqa: E402
from app.database import Base  # noqa: E402
from app.database import get_db  # noqa: E402
from app.seed import seed_admin  # noqa: E402
from app.services.vector_store import InMemoryVectorStore  # noqa: E402
from tests.fakes import FakeLLMClient  # noqa: E402
from tests.fakes import OfflineAgent  # noqa: E402


@pytest.fixture
def fake_vector_store() -> InMemoryVectorStore:
    """Empty in-memory store; tests add documents as needed."""
    return InMemoryVectorStore()


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def offline_agent(
    fake_vector_store: InMemoryVectorStore,
) -> OfflineAgent:
    return OfflineAgent(vector_store=fake_vector_store)


@pytest.fixture
def fake_redis_server() -> fakeredis.FakeServer:
    """Shared FakeServer so async HTTP and sync TestClient see one Redis."""
    return fakeredis.FakeServer()


@pytest_asyncio.fixture
async def fake_redis(
    fake_redis_server: fakeredis.FakeServer,
) -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(
        server=fake_redis_server,
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest_asyncio.fixture
async def db_engine():
    """Shared in-memory SQLite so all connections see the same schema."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
    )
    async with factory() as session:
        await seed_admin(session)
        yield session


@pytest_asyncio.fixture
async def app(
    db_engine,
    fake_redis_server: fakeredis.FakeServer,
    offline_agent: OfflineAgent,
    monkeypatch: pytest.MonkeyPatch,
):
    """FastAPI app wired to SQLite + FakeRedis + OfflineAgent."""
    session_factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        await seed_admin(session)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def _get_redis():
        # New client per call: TestClient runs WS on another loop;
        # FakeServer keeps ticket state shared across clients.
        return fakeredis.aioredis.FakeRedis(
            server=fake_redis_server,
            decode_responses=True,
        )

    async def _noop_init_db() -> None:
        # Lifespan must not open the process-global engine / Postgres.
        return None

    monkeypatch.setattr(
        "app.database.AsyncSessionLocal",
        session_factory,
    )

    import app.routes.auth as auth_routes
    import app.routes.chat as chat_routes
    import app.services.ingest_jobs as ingest_jobs
    import app.services.rate_limit as rate_limit

    monkeypatch.setattr(
        chat_routes,
        "AsyncSessionLocal",
        session_factory,
    )
    monkeypatch.setattr(
        ingest_jobs,
        "AsyncSessionLocal",
        session_factory,
    )
    monkeypatch.setattr("app.redis_client.get_redis", _get_redis)
    monkeypatch.setattr(rate_limit, "get_redis", _get_redis)
    monkeypatch.setattr(auth_routes, "get_redis", _get_redis)
    monkeypatch.setattr(chat_routes, "get_redis", _get_redis)
    monkeypatch.setattr("app.main.init_db", _noop_init_db)

    override_agent(offline_agent)
    try:
        from app.main import app as fastapi_app

        fastapi_app.dependency_overrides[get_db] = (
            _override_get_db
        )
        yield fastapi_app
        fastapi_app.dependency_overrides.clear()
    finally:
        override_agent(None)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
