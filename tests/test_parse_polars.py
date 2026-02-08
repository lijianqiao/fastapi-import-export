"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_parse_polars.py
@DateTime: 2026-02-08
@Docs: Tests for parse_polars.py module.
parse_polars.py 模块测试。
"""

from pathlib import Path

import polars as pl
import pytest

from fastapi_import_export.exceptions import ParseError
from fastapi_import_export.parse_polars import (
    dataframe_to_preview_rows,
    normalize_columns,
    parse_tabular_file,
)


class TestParseTabularFile:
    """Tests for parse_tabular_file.
    parse_tabular_file 测试。
    """

    def test_csv_normal(self, sample_csv_path: Path) -> None:
        """Parse a normal CSV / 解析正常 CSV。"""
        result = parse_tabular_file(sample_csv_path, filename="sample.csv")
        assert result.total_rows == 5
        assert "row_number" in result.df.columns
        # row_number starts at 1 / row_number 从 1 开始
        assert result.df.get_column("row_number").to_list()[0] == 1

    def test_xlsx_normal(self, sample_xlsx_path: Path) -> None:
        """Parse a normal XLSX / 解析正常 XLSX。"""
        result = parse_tabular_file(sample_xlsx_path, filename="sample.xlsx")
        assert result.total_rows == 5
        assert "row_number" in result.df.columns

    def test_empty_file_raises(self, empty_csv_path: Path) -> None:
        """Empty file raises an error / 空文件抛出异常。"""
        with pytest.raises((ParseError, pl.exceptions.NoDataError)):
            parse_tabular_file(empty_csv_path, filename="empty.csv")

    def test_chinese_headers(self, chinese_csv_path: Path) -> None:
        """Parse CSV with Chinese headers / 解析中文表头 CSV。"""
        result = parse_tabular_file(chinese_csv_path, filename="chinese_headers.csv")
        assert result.total_rows == 3
        assert "用户名" in result.df.columns

    def test_csv_columns_present(self, sample_csv_path: Path) -> None:
        """CSV columns are correctly parsed / CSV 列被正确解析。"""
        result = parse_tabular_file(sample_csv_path, filename="sample.csv")
        assert "username" in result.df.columns
        assert "email" in result.df.columns
        assert "age" in result.df.columns


class TestNormalizeColumns:
    """Tests for normalize_columns.
    normalize_columns 测试。
    """

    def test_renames_columns(self) -> None:
        """Rename columns using mapping / 使用映射重命名列。"""
        df = pl.DataFrame({"A": [1], "B": [2], "C": [3]})
        result = normalize_columns(df, {"A": "alpha", "B": "beta"})
        assert "alpha" in result.columns
        assert "beta" in result.columns
        # Unmatched column preserved / 未匹配列保留
        assert "C" in result.columns

    def test_no_mapping_returns_same(self) -> None:
        """Empty mapping returns same columns / 空映射返回相同列。"""
        df = pl.DataFrame({"X": [1]})
        result = normalize_columns(df, {})
        assert result.columns == ["X"]


class TestDataframeToPreviewRows:
    """Tests for dataframe_to_preview_rows.
    dataframe_to_preview_rows 测试。
    """

    def test_returns_list_of_dicts(self, sample_polars_df: pl.DataFrame) -> None:
        """Return list[dict] / 返回 list[dict]。"""
        rows = dataframe_to_preview_rows(sample_polars_df)
        assert isinstance(rows, list)
        assert len(rows) == 5
        assert isinstance(rows[0], dict)

    def test_contains_all_columns(self, sample_polars_df: pl.DataFrame) -> None:
        """All columns present in each row dict / 每行字典包含所有列。"""
        rows = dataframe_to_preview_rows(sample_polars_df)
        for row in rows:
            assert "username" in row
            assert "email" in row
