"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_schemas.py
@DateTime: 2026-02-08
@Docs: Tests for schemas.py module.
schemas.py 模块测试。
"""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fastapi_import_export.schemas import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportErrorItem,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportValidateResponse,
)


class TestImportErrorItem:
    """Tests for ImportErrorItem.
    ImportErrorItem 测试。
    """

    def test_required_fields(self) -> None:
        """Required fields enforced / 必填字段校验。"""
        item = ImportErrorItem(row_number=1, message="bad value")
        assert item.row_number == 1
        assert item.message == "bad value"
        assert item.field is None

    def test_missing_required_raises(self) -> None:
        """Missing required field raises ValidationError / 缺少必填字段时抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            ImportErrorItem(row_number=1)  # type: ignore[call-arg]

    def test_json_roundtrip(self) -> None:
        """JSON serialization roundtrip / JSON 序列化往返。"""
        item = ImportErrorItem(row_number=2, field="email", message="invalid")
        json_str = item.model_dump_json()
        restored = ImportErrorItem.model_validate_json(json_str)
        assert restored == item


class TestImportValidateResponse:
    """Tests for ImportValidateResponse.
    ImportValidateResponse 测试。
    """

    def test_defaults(self) -> None:
        """errors defaults to empty list / errors 默认空列表。"""
        resp = ImportValidateResponse(
            import_id=uuid4(),
            checksum="abc",
            total_rows=10,
            valid_rows=8,
            error_rows=2,
        )
        assert resp.errors == []

    def test_json_roundtrip(self) -> None:
        uid = uuid4()
        resp = ImportValidateResponse(
            import_id=uid,
            checksum="sha256hash",
            total_rows=100,
            valid_rows=95,
            error_rows=5,
            errors=[ImportErrorItem(row_number=1, message="err")],
        )
        restored = ImportValidateResponse.model_validate_json(resp.model_dump_json())
        assert restored.import_id == uid
        assert len(restored.errors) == 1


class TestImportPreviewRow:
    """Tests for ImportPreviewRow.
    ImportPreviewRow 测试。
    """

    def test_data_is_dict(self) -> None:
        row = ImportPreviewRow(row_number=1, data={"name": "alice"})
        assert row.data == {"name": "alice"}


class TestImportPreviewResponse:
    """Tests for ImportPreviewResponse.
    ImportPreviewResponse 测试。
    """

    def test_json_roundtrip(self) -> None:
        resp = ImportPreviewResponse(
            import_id=uuid4(),
            checksum="abc",
            page=1,
            page_size=50,
            total_rows=100,
            rows=[ImportPreviewRow(row_number=1, data={"a": 1})],
        )
        restored = ImportPreviewResponse.model_validate_json(resp.model_dump_json())
        assert restored.page == 1
        assert len(restored.rows) == 1


class TestImportCommitRequest:
    """Tests for ImportCommitRequest.
    ImportCommitRequest 测试。
    """

    def test_allow_overwrite_default_false(self) -> None:
        req = ImportCommitRequest(import_id=uuid4(), checksum="abc")
        assert req.allow_overwrite is False

    def test_json_roundtrip(self) -> None:
        req = ImportCommitRequest(import_id=uuid4(), checksum="abc", allow_overwrite=True)
        restored = ImportCommitRequest.model_validate_json(req.model_dump_json())
        assert restored.allow_overwrite is True


class TestImportCommitResponse:
    """Tests for ImportCommitResponse.
    ImportCommitResponse 测试。
    """

    def test_json_roundtrip(self) -> None:
        resp = ImportCommitResponse(
            import_id=uuid4(),
            checksum="abc",
            status="committed",
            imported_rows=100,
            created_at=datetime.now(),
        )
        restored = ImportCommitResponse.model_validate_json(resp.model_dump_json())
        assert restored.status == "committed"
        assert restored.imported_rows == 100
