"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: conftest.py
@DateTime: 2026-02-08
@Docs: Test fixtures for SQLAlchemy E2E tests.
SQLAlchemy E2E 测试 fixtures。
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .app import create_app
from .models import Base

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
async def db_session(tmp_path: Path) -> AsyncGenerator[tuple[async_sessionmaker[AsyncSession], str], None]:
    """Create an in-memory SQLite engine and yield a session factory + base_dir.
    创建 SQLite 内存引擎并返回会话工厂 + base_dir。
    """
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    base_dir = str(tmp_path / "import_export")
    yield factory, base_dir

    await engine.dispose()


@pytest.fixture
async def client(db_session: tuple[async_sessionmaker[AsyncSession], str]) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient for the test app.
    提供测试应用的 httpx AsyncClient。
    """
    factory, base_dir = db_session
    app = create_app(session_factory=factory, base_dir=base_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def csv_path() -> Path:
    return FIXTURES_DIR / "devices.csv"


@pytest.fixture
def xlsx_path() -> Path:
    return FIXTURES_DIR / "devices.xlsx"
