"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_contrib_tortoise.py
@DateTime: 2026-02-09
@Docs: Tests for Tortoise ORM contrib adapters.
Tortoise ORM 适配层测试。
"""

import pytest

from fastapi_import_export.error_codes import DB_CONFLICT
from fastapi_import_export.importer import ImportStatus
from fastapi_import_export.options import ImportOptions
from tests.conftest import make_upload_file

pytest.importorskip("tortoise")
from tortoise import Tortoise, fields, models

from fastapi_import_export.contrib.tortoise import export_model_csv, import_model_csv


class Book(models.Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=100)
    isbn = fields.CharField(max_length=20, unique=True)

    class Meta(models.Model.Meta):
        table = "books_tortoise"


@pytest.mark.asyncio
async def test_contrib_tortoise_import_export() -> None:
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": [__name__]})
    await Tortoise.generate_schemas()

    try:
        csv = "title,isbn\nC,333\n"
        file = make_upload_file("books.csv", csv.encode())
        result = await import_model_csv(file, model=Book, unique_fields=["isbn"])
        assert result.status == ImportStatus.COMMITTED
        assert result.imported_rows == 1

        payload = await export_model_csv(model=Book)
        data = b"".join([chunk async for chunk in payload.stream])
        assert b"title" in data
        assert b"333" in data
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
async def test_contrib_tortoise_duplicate_conflict_error_code() -> None:
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": [__name__]})
    await Tortoise.generate_schemas()

    try:
        file1 = make_upload_file("books.csv", b"title,isbn\nA,111\n")
        result1 = await import_model_csv(file1, model=Book, unique_fields=["isbn"])
        assert result1.status == ImportStatus.COMMITTED

        file2 = make_upload_file("books.csv", b"title,isbn\nB,111\n")
        result2 = await import_model_csv(file2, model=Book, unique_fields=["isbn"])
        assert result2.status == ImportStatus.VALIDATED
        assert result2.errors
        assert result2.errors[0].type == DB_CONFLICT
    finally:
        await Tortoise.close_connections()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overwrite_mode", "expected_allow_overwrite"),
    [
        ("reject", False),
        ("upsert", True),
        ("replace", True),
    ],
)
async def test_contrib_tortoise_overwrite_mode_matrix(overwrite_mode: str, expected_allow_overwrite: bool) -> None:
    """overwrite_mode should propagate to Tortoise adapter persist handler.
    overwrite_mode 应透传到 Tortoise 适配层持久化处理器。
    """
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": [__name__]})
    await Tortoise.generate_schemas()

    captured_flags: list[bool] = []

    async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
        captured_flags.append(bool(allow_overwrite))
        return int(valid_df.height)

    try:
        file = make_upload_file("books.csv", b"title,isbn\nMatrix,303\n")
        result = await import_model_csv(
            file,
            model=Book,
            unique_fields=["isbn"],
            options=ImportOptions(overwrite_mode=overwrite_mode),
            persist_fn=persist_fn,
        )
        assert result.status == ImportStatus.COMMITTED
        assert result.imported_rows == 1
        assert captured_flags == [expected_allow_overwrite]
    finally:
        await Tortoise.close_connections()
