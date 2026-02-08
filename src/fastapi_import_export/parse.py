"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: parse.py
@DateTime: 2026-02-08
@Docs: Parse module facade with optional backend.
解析模块门面（可选后端）。
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi_import_export.exceptions import ImportExportError


def _load_backend() -> Any:
    try:
        from fastapi_import_export import parse_polars

        return parse_polars
    except Exception as exc:  # pragma: no cover / 覆盖忽略
        raise ImportExportError(
            message="Missing optional dependencies for parsing. Install extras: polars,xlsx / 缺少解析可选依赖，请安装: polars,xlsx",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


def parse_tabular_file(file_path: Path, *, filename: str) -> Any:
    """
    Parse a CSV/Excel file to ParsedTable.
    将 CSV/Excel 文件解析为 ParsedTable。

    Args:
        file_path: File path on disk.
        file_path: 文件磁盘路径。
        filename: Original filename.
        filename: 原始文件名。

    Returns:
        ParsedTable: Parsed result.
        ParsedTable: 解析结果。
    """
    backend = _load_backend()
    return backend.parse_tabular_file(file_path, filename=filename)


def normalize_columns(df: Any, column_mapping: dict[str, str]) -> Any:
    """
    Normalize column names using a mapping table.
    基于列名映射表标准化列名。

    Args:
        df: Input DataFrame.
        df: 输入 DataFrame。
        column_mapping: Mapping from raw header to canonical header.
        column_mapping: 列名映射（原始表头 -> 规范表头）。

    Returns:
        DataFrame: Renamed DataFrame.
        DataFrame: 重命名后的 DataFrame。
    """
    backend = _load_backend()
    return backend.normalize_columns(df, column_mapping)


def dataframe_to_preview_rows(df: Any) -> list[dict[str, Any]]:
    """
    Convert a DataFrame to preview rows.
    将 DataFrame 转换为预览行。

    Args:
        df: Input DataFrame.
        df: 输入 DataFrame。

    Returns:
        list[dict[str, Any]]: Preview rows.
        list[dict[str, Any]]: 预览行列表。
    """
    backend = _load_backend()
    return backend.dataframe_to_preview_rows(df)


if TYPE_CHECKING:
    from fastapi_import_export.parse_polars import ParsedTable as ParsedTable
else:

    class ParsedTable:  # noqa: D101 / no docstring / 无需文档字符串
        """
        ParsedTable placeholder when optional backend is missing.
        可选后端缺失时的 ParsedTable 占位类型。
        """
