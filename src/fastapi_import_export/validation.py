"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: validation.py
@DateTime: 2026-02-08
@Docs: Validation facade with optional backend.
校验门面（可选后端）。
"""

from collections.abc import Iterable
from typing import Any

from fastapi_import_export.exceptions import ImportExportError


def _load_backend() -> Any:
    try:
        from fastapi_import_export import validation_polars

        return validation_polars
    except Exception as exc:  # pragma: no cover / 覆盖忽略
        raise ImportExportError(
            message="Missing optional dependencies for validation. Install extras: polars / 缺少校验可选依赖，请安装: polars",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


def collect_infile_duplicates(df: Any, unique_fields: Iterable[str]) -> list[dict[str, Any]]:
    """
    Collect duplicate values within a file.
    收集文件内重复值。

    Args:
        df: Input DataFrame.
        df: 输入数据框。
        unique_fields: Fields to check.
        unique_fields: 要检查的字段列表。

    Returns:
        list[dict[str, Any]]: Error list.
        list[dict[str, Any]]: 错误列表。
    """
    backend = _load_backend()
    return backend.collect_infile_duplicates(df, unique_fields)


def build_conflict_errors(df: Any, field: str, conflict_values: Iterable[str], *, reason: str) -> list[dict[str, Any]]:
    """
    Build conflict error list.
    构建冲突错误列表。

    Args:
        df: Input DataFrame.
        df: 输入数据框。
        field: Conflict field name.
        field: 冲突字段名。
        conflict_values: Conflict values.
        conflict_values: 冲突值列表。
        reason: Conflict reason.
        reason: 冲突原因。

    Returns:
        list[dict[str, Any]]: Error list.
        list[dict[str, Any]]: 错误列表。
    """
    backend = _load_backend()
    return backend.build_conflict_errors(df, field, conflict_values, reason=reason)
