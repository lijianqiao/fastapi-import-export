"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: conftest.py
@DateTime: 2026-02-08
@Docs: Test fixtures for Tortoise ORM E2E tests.
Tortoise ORM E2E 测试 fixtures。
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from .app import create_app

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
async def tortoise_db(tmp_path: Path) -> AsyncGenerator[str, None]:
    """Initialize Tortoise ORM with in-memory SQLite.
    使用 SQLite 内存数据库初始化 Tortoise ORM。
    """
    base_dir = str(tmp_path / "import_export")
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["examples.tortoise_app.models"]},
    )
    await Tortoise.generate_schemas()
    yield base_dir
    await Tortoise.close_connections()


@pytest.fixture
async def client(tortoise_db: str) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient for the Tortoise test app.
    提供 Tortoise 测试应用的 httpx AsyncClient。
    """
    app = create_app(base_dir=tortoise_db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def csv_path() -> Path:
    return FIXTURES_DIR / "devices.csv"


@pytest.fixture
def xlsx_path() -> Path:
    return FIXTURES_DIR / "devices.xlsx"
