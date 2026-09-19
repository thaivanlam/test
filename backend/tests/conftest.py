import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use SQLite for tests before app modules initialize their default engine.
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.api.deps import get_redis
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class FakeRedis:
    """In-memory stand-in for RedisClient, backed by a dict.

    The previous MagicMock returned None from get() and was rebuilt on every
    request, so a value written by one request was never visible to the next.
    That made cache behaviour — including cross-user cache leaks — impossible
    to observe from a test. This fake keeps its store across requests, which is
    the property under test.

    Expiry is ignored: these tests assert on what is cached under which key,
    not on when it lapses.
    """

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value

    async def delete(self, key: str):
        self.store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.store


fake_redis = FakeRedis()


@pytest.fixture(autouse=True)
def reset_redis():
    """Keep cache state from leaking between tests."""
    fake_redis.store.clear()
    yield
    fake_redis.store.clear()


def override_get_redis():
    return fake_redis


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis] = override_get_redis


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session


@pytest.fixture
def auth_headers() -> dict:
    """Create auth headers with a valid token for testing."""
    token = create_access_token(data={"sub": "00000000-0000-0000-0000-000000000001"})
    return {"Authorization": f"Bearer {token}"}
