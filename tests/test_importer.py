"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_importer.py
@DateTime: 2026-02-08
@Docs: Tests for importer.py module.
importer.py 模块测试。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile

from fastapi_import_export.importer import Importer, ImportStatus
from fastapi_import_export.resource import Resource
from fastapi_import_export.schemas import ImportErrorItem


class DummyResource(Resource):
    """Dummy resource for testing / 测试用虚拟资源。"""

    name: str
    field_aliases = {"Name": "name"}


class TestImporter:
    """Tests for Importer class.
    Importer 类测试。
    """

    @pytest.mark.asyncio
    async def test_import_data_success(self) -> None:
        """Full lifecycle success: parse->validate->transform->persist / 完整生命周期成功。"""
        parser = AsyncMock(return_value=[{"name": "alice"}])
        validator = AsyncMock(return_value=([{"name": "alice"}], []))
        transformer = AsyncMock(return_value=[{"name": "alice"}])
        persister = AsyncMock(return_value=1)

        importer = Importer(parser=parser, validator=validator, transformer=transformer, persister=persister)
        file = MagicMock(spec=UploadFile)
        result = await importer.import_data(file=file, resource=DummyResource)

        assert result.status == ImportStatus.COMMITTED
        assert result.imported_rows == 1
        assert result.errors == []
        transformer.assert_called_once()
        persister.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_data_with_validation_errors(self) -> None:
        """Validation errors skip transform/persist / 校验错误跳过 transform/persist。"""
        error = ImportErrorItem(row_number=1, field="name", message="required")
        parser = AsyncMock(return_value=[{}])
        validator = AsyncMock(return_value=([], [error]))
        transformer = AsyncMock()
        persister = AsyncMock()

        importer = Importer(parser=parser, validator=validator, transformer=transformer, persister=persister)
        file = MagicMock(spec=UploadFile)
        result = await importer.import_data(file=file, resource=DummyResource)

        assert result.status == ImportStatus.VALIDATED
        assert result.imported_rows == 0
        assert len(result.errors) == 1
        transformer.assert_not_called()
        persister.assert_not_called()

    @pytest.mark.asyncio
    async def test_parse_delegates(self) -> None:
        """parse() delegates to parser / parse() 正确代理。"""
        parser = AsyncMock(return_value="parsed_data")
        importer = Importer(
            parser=parser,
            validator=AsyncMock(),
            transformer=AsyncMock(),
            persister=AsyncMock(),
        )
        file = MagicMock(spec=UploadFile)
        result = await importer.parse(file=file, resource=DummyResource)
        assert result == "parsed_data"

    @pytest.mark.asyncio
    async def test_validate_delegates(self) -> None:
        """validate() delegates to validator / validate() 正确代理。"""
        validator = AsyncMock(return_value=([], []))
        importer = Importer(
            parser=AsyncMock(),
            validator=validator,
            transformer=AsyncMock(),
            persister=AsyncMock(),
        )
        result = await importer.validate(data="data", resource=DummyResource, allow_overwrite=False)
        assert result == ([], [])

    @pytest.mark.asyncio
    async def test_transform_delegates(self) -> None:
        """transform() delegates to transformer / transform() 正确代理。"""
        transformer = AsyncMock(return_value="transformed")
        importer = Importer(
            parser=AsyncMock(),
            validator=AsyncMock(),
            transformer=transformer,
            persister=AsyncMock(),
        )
        result = await importer.transform(data="data", resource=DummyResource)
        assert result == "transformed"

    @pytest.mark.asyncio
    async def test_persist_delegates(self) -> None:
        """persist() delegates to persister / persist() 正确代理。"""
        persister = AsyncMock(return_value=42)
        importer = Importer(
            parser=AsyncMock(),
            validator=AsyncMock(),
            transformer=AsyncMock(),
            persister=persister,
        )
        result = await importer.persist(data="data", resource=DummyResource, allow_overwrite=True)
        assert result == 42
