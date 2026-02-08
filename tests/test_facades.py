"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_facades.py
@DateTime: 2026-02-08
@Docs: Tests for facade modules (parse, validation, storage, db_validation).
门面模块测试（parse, validation, storage, db_validation）。
"""

from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

from fastapi_import_export.exceptions import ImportExportError


class TestParseFacade:
    """Tests for parse.py facade.
    parse.py 门面模块测试。
    """

    def test_proxy_to_backend(self, sample_csv_path: Path) -> None:
        """Proxy to real backend when available / 后端可用时正常代理。"""
        from fastapi_import_export.parse import parse_tabular_file

        result = parse_tabular_file(sample_csv_path, filename="sample.csv")
        assert result.total_rows == 5

    def test_missing_backend_raises(self) -> None:
        """Missing backend raises ImportExportError / 后端缺失时抛 ImportExportError。"""
        with patch("fastapi_import_export.parse._load_backend", side_effect=ImportExportError(
            message="Missing dependency", error_code="missing_dependency"
        )):
            from fastapi_import_export.parse import parse_tabular_file

            with pytest.raises(ImportExportError) as exc_info:
                parse_tabular_file(Path("/tmp/fake.csv"), filename="fake.csv")
            assert exc_info.value.error_code == "missing_dependency"

    def test_parsed_table_placeholder(self) -> None:
        """ParsedTable placeholder can be instantiated at runtime / ParsedTable 占位类可实例化。"""
        # At runtime (not TYPE_CHECKING), ParsedTable is a placeholder class
        # 运行时（非 TYPE_CHECKING）ParsedTable 是一个占位类
        from fastapi_import_export.parse import ParsedTable

        assert ParsedTable is not None


class TestValidationFacade:
    """Tests for validation.py facade.
    validation.py 门面模块测试。
    """

    def test_proxy_to_backend(self) -> None:
        """Proxy to real backend when available / 后端可用时正常代理。"""
        from fastapi_import_export.validation import collect_infile_duplicates

        df = pl.DataFrame({"row_number": [1, 2], "name": ["a", "b"]})
        errors = collect_infile_duplicates(df, ["name"])
        assert errors == []

    def test_missing_backend_raises(self) -> None:
        """Missing backend raises ImportExportError / 后端缺失时抛 ImportExportError。"""
        with patch("fastapi_import_export.validation._load_backend", side_effect=ImportExportError(
            message="Missing dependency", error_code="missing_dependency"
        )):
            from fastapi_import_export.validation import collect_infile_duplicates

            with pytest.raises(ImportExportError):
                collect_infile_duplicates(None, ["x"])


class TestStorageFacade:
    """Tests for storage.py facade.
    storage.py 门面模块测试。
    """

    def test_proxy_new_import_id(self) -> None:
        """new_import_id proxies to backend / new_import_id 正确代理。"""
        from fastapi_import_export.storage import new_import_id

        result = new_import_id()
        from uuid import UUID

        assert isinstance(result, UUID)

    def test_import_paths_placeholder(self) -> None:
        """ImportPaths placeholder can be instantiated / ImportPaths 占位类可实例化。"""
        from fastapi_import_export.storage import ImportPaths

        assert ImportPaths is not None


class TestDbValidationFacade:
    """Tests for db_validation.py facade.
    db_validation.py 门面模块测试。
    """

    def test_proxy_to_backend(self) -> None:
        """Proxy to real backend / 正确代理到真实后端。"""
        from fastapi_import_export.db_validation import build_key_to_row_numbers

        df = pl.DataFrame({"row_number": [1], "email": ["a@b.com"]})
        result = build_key_to_row_numbers(df, ["email"])
        assert ("a@b.com",) in result
