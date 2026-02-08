"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_exporter.py
@DateTime: 2026-02-08
@Docs: Tests for exporter.py module.
exporter.py 模块测试。
"""

from unittest.mock import AsyncMock

import pytest

from fastapi_import_export.exporter import Exporter, ExportPayload
from fastapi_import_export.resource import Resource


class DummyResource(Resource):
    """Dummy resource for testing / 测试用虚拟资源。"""

    name: str


async def _dummy_stream():
    """Dummy async byte stream / 虚拟异步字节流。"""
    yield b"hello"


class TestExporter:
    """Tests for Exporter class.
    Exporter 类测试。
    """

    @pytest.mark.asyncio
    async def test_stream_full_lifecycle(self) -> None:
        """Full lifecycle: query->serialize->render->ExportPayload / 完整生命周期。"""
        query_fn = AsyncMock(return_value=[{"name": "alice"}])
        serialize_fn = AsyncMock(return_value=b"csv_data")
        render_fn = AsyncMock(return_value=_dummy_stream())

        exporter = Exporter(query_fn=query_fn, serialize_fn=serialize_fn, render_fn=render_fn)
        result = await exporter.stream(
            resource=DummyResource,
            fmt="csv",
            filename="export.csv",
            media_type="text/csv",
        )

        assert isinstance(result, ExportPayload)
        assert result.filename == "export.csv"
        assert result.media_type == "text/csv"
        query_fn.assert_called_once()
        serialize_fn.assert_called_once()
        render_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_delegates(self) -> None:
        """query() delegates to query_fn / query() 正确代理。"""
        query_fn = AsyncMock(return_value="data")
        exporter = Exporter(query_fn=query_fn, serialize_fn=AsyncMock(), render_fn=AsyncMock())
        result = await exporter.query(resource=DummyResource)
        assert result == "data"

    @pytest.mark.asyncio
    async def test_serialize_delegates(self) -> None:
        """serialize() delegates to serialize_fn / serialize() 正确代理。"""
        serialize_fn = AsyncMock(return_value=b"bytes")
        exporter = Exporter(query_fn=AsyncMock(), serialize_fn=serialize_fn, render_fn=AsyncMock())
        result = await exporter.serialize(data="data", fmt="csv")
        assert result == b"bytes"

    def test_export_payload_attributes(self) -> None:
        """ExportPayload attributes correct / ExportPayload 属性正确。"""
        payload = ExportPayload(filename="f.csv", media_type="text/csv", stream=_dummy_stream())
        assert payload.filename == "f.csv"
        assert payload.media_type == "text/csv"
