"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_contrib_sqlmodel.py
@DateTime: 2026-02-09
@Docs: Tests for SQLModel contrib adapters.
SQLModel 适配层测试。
"""

import pytest

from fastapi_import_export.contrib.sqlmodel import export_model_csv, import_model_csv
from fastapi_import_export.importer import ImportStatus
from tests.conftest import make_upload_file


@pytest.mark.asyncio
async def test_contrib_sqlmodel_import_export() -> None:
    pytest.importorskip("sqlmodel")
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("aiosqlite")
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlmodel import Field, SQLModel

    class Book(SQLModel, table=True):
        __tablename__ = "books_sqlmodel"  # type: ignore[assignment]  # type checker ignore / 类型检查忽略
        id: int | None = Field(default=None, primary_key=True)
        title: str
        isbn: str

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        csv = "title,isbn\nB,222\n"
        file = make_upload_file("books.csv", csv.encode())
        result = await import_model_csv(file, model=Book, db=session, unique_fields=["isbn"])
        assert result.status == ImportStatus.COMMITTED
        assert result.imported_rows == 1

        payload = await export_model_csv(model=Book, db=session)
        data = b"".join([chunk async for chunk in payload.stream])
        assert b"title" in data
        assert b"222" in data
