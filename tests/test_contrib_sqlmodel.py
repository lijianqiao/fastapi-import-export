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
from fastapi_import_export.error_codes import DB_CONFLICT
from fastapi_import_export.importer import ImportStatus
from fastapi_import_export.options import ImportOptions
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


@pytest.mark.asyncio
async def test_contrib_sqlmodel_duplicate_conflict_error_code() -> None:
    pytest.importorskip("sqlmodel")
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("aiosqlite")
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlmodel import Field, SQLModel

    class BookDuplicate(SQLModel, table=True):
        __tablename__ = "books_sqlmodel_dup"  # type: ignore[assignment]
        id: int | None = Field(default=None, primary_key=True)
        title: str
        isbn: str

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        file1 = make_upload_file("books.csv", b"title,isbn\nA,111\n")
        result1 = await import_model_csv(file1, model=BookDuplicate, db=session, unique_fields=["isbn"])
        assert result1.status == ImportStatus.COMMITTED

        file2 = make_upload_file("books.csv", b"title,isbn\nB,111\n")
        result2 = await import_model_csv(file2, model=BookDuplicate, db=session, unique_fields=["isbn"])
        assert result2.status == ImportStatus.VALIDATED
        assert result2.errors
        assert result2.errors[0].type == DB_CONFLICT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overwrite_mode", "expected_allow_overwrite"),
    [
        ("reject", False),
        ("upsert", True),
        ("replace", True),
    ],
)
async def test_contrib_sqlmodel_overwrite_mode_matrix(overwrite_mode: str, expected_allow_overwrite: bool) -> None:
    """overwrite_mode should propagate to SQLModel adapter persist handler.
    overwrite_mode 应透传到 SQLModel 适配层持久化处理器。
    """
    pytest.importorskip("sqlmodel")
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("aiosqlite")
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlmodel import Field, SQLModel

    if overwrite_mode == "reject":

        class BookMatrixReject(SQLModel, table=True):
            __tablename__ = "books_sqlmodel_mode_reject"  # type: ignore[assignment]
            id: int | None = Field(default=None, primary_key=True)
            title: str
            isbn: str

        model_cls = BookMatrixReject
    elif overwrite_mode == "upsert":

        class BookMatrixUpsert(SQLModel, table=True):
            __tablename__ = "books_sqlmodel_mode_upsert"  # type: ignore[assignment]
            id: int | None = Field(default=None, primary_key=True)
            title: str
            isbn: str

        model_cls = BookMatrixUpsert
    else:

        class BookMatrixReplace(SQLModel, table=True):
            __tablename__ = "books_sqlmodel_mode_replace"  # type: ignore[assignment]
            id: int | None = Field(default=None, primary_key=True)
            title: str
            isbn: str

        model_cls = BookMatrixReplace

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    captured_flags: list[bool] = []

    async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
        captured_flags.append(bool(allow_overwrite))
        return int(valid_df.height)

    async with async_session() as session:
        file = make_upload_file("books.csv", b"title,isbn\nMatrix,202\n")
        result = await import_model_csv(
            file,
            model=model_cls,
            db=session,
            unique_fields=["isbn"],
            options=ImportOptions(overwrite_mode=overwrite_mode),
            persist_fn=persist_fn,
        )
        assert result.status == ImportStatus.COMMITTED
        assert result.imported_rows == 1
        assert captured_flags == [expected_allow_overwrite]
