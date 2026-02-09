"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_easy.py
@DateTime: 2026-02-09
@Docs: Tests for easy-layer APIs.
易用层 API 测试。
"""

import polars as pl
import pytest

from fastapi_import_export import export_csv, export_xlsx, import_csv
from fastapi_import_export.importer import ImportStatus
from fastapi_import_export.options import ExportOptions
from fastapi_import_export.resource import Resource
from fastapi_import_export.serializers import CsvSerializer
from tests.conftest import make_upload_file


class UserResource(Resource):
    id: int | None = None
    username: str
    email: str


@pytest.mark.asyncio
async def test_easy_export_csv_rows() -> None:
    rows = [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}]
    payload = await export_csv(rows, resource=UserResource)
    data = b"".join([chunk async for chunk in payload.stream])
    assert payload.filename.endswith(".csv")
    assert b"id,username" in data
    assert not data.startswith(b"\xef\xbb\xbf")


@pytest.mark.asyncio
async def test_easy_export_xlsx_rows() -> None:
    pytest.importorskip("openpyxl")
    rows = [{"id": 1, "username": "alice"}]
    payload = await export_xlsx(rows, resource=UserResource)
    data = b"".join([chunk async for chunk in payload.stream])
    assert payload.filename.endswith(".xlsx")
    assert len(data) > 0


@pytest.mark.asyncio
async def test_easy_import_csv_success() -> None:
    csv = "username,email\nalice,alice@b.com\n"
    file = make_upload_file("test.csv", csv.encode())

    async def validate_fn(db, df, *, allow_overwrite: bool = False):
        return df, []

    async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
        return int(valid_df.height)

    result = await import_csv(
        file,
        resource=UserResource,
        validate_fn=validate_fn,
        persist_fn=persist_fn,
    )
    assert result.status == ImportStatus.COMMITTED
    assert result.imported_rows == 1


@pytest.mark.asyncio
async def test_easy_import_csv_validation_error() -> None:
    csv = "username,email\n,alice@b.com\n"
    file = make_upload_file("test.csv", csv.encode())

    async def validate_fn(db, df, *, allow_overwrite: bool = False):
        errors = [{"row_number": 1, "field": "username", "message": "required"}]
        valid_df = df.filter(pl.col("row_number") != 1)
        return valid_df, errors

    async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
        return int(valid_df.height)

    result = await import_csv(
        file,
        resource=UserResource,
        validate_fn=validate_fn,
        persist_fn=persist_fn,
    )
    assert result.status == ImportStatus.VALIDATED
    assert len(result.errors) == 1


def test_serializer_csv_default_no_bom() -> None:
    rows = [{"a": 1}]
    data = CsvSerializer().serialize(data=rows, options=ExportOptions())
    assert not data.startswith(b"\xef\xbb\xbf")
