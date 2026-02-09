"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_contrib_tortoise.py
@DateTime: 2026-02-09
@Docs: Tests for Tortoise ORM contrib adapters.
Tortoise ORM 适配层测试。
"""

import pytest

from fastapi_import_export.importer import ImportStatus
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
