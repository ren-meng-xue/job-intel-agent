import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 导入所有模型确保 Base.metadata 完整
import app.models.auth_session  # noqa: F401
import app.models.job  # noqa: F401
import app.models.report  # noqa: F401
import app.models.user  # noqa: F401
from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5434/job_intel_test"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestAsyncSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def db():
    """每个测试创建表、清理数据（通过 dispose 避免连接冲突）"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSession() as session:
        yield session

    await test_engine.dispose()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """注入测试 DB session"""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
