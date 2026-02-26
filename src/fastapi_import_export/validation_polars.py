"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: validation_polars.py
@DateTime: 2026-02-08
@Docs: Polars-backed validation helpers.
基于 Polars 的校验辅助。
"""

from collections.abc import Iterable
from typing import Any

import polars as pl

from fastapi_import_export.error_codes import SCHEMA_ERROR


def _normalize_text(value: Any) -> str | None:
    """Normalize a value for duplicate/conflict comparison.
    标准化值以进行重复/冲突比较。


    Rules:
        - None -> None
        - blank string -> None
        - other values -> stripped string representation
    规则:
        - None -> None
        - 空字符串 -> None
        - 其他值 -> 去除空白的字符串表示
    Args:
    value: Input value.
        输入值。
    Returns:
    str | None: Normalized string or None.
        规范化后的字符串或 None。

    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def collect_infile_duplicates(df: pl.DataFrame, unique_fields: Iterable[str]) -> list[dict[str, Any]]:
    """
    Collect duplicate values within a file.
    收集文件内重复值。

    Args:
        df: Input DataFrame (must contain row_number).
        df: 输入数据框（必须包含 row_number）。
        unique_fields: Fields to check.
        unique_fields: 要检查的字段列表。

    Returns:
        list[dict[str, Any]]: Error list.
        list[dict[str, Any]]: 错误列表。
    """
    errors: list[dict[str, Any]] = []
    if df.is_empty():
        return errors
    cols = set(df.columns)
    for field in unique_fields:
        if field not in cols:
            continue
        dup_values = {
            normalized
            for value in (
                df.group_by(field).agg(pl.len().alias("count")).filter(pl.col("count") > 1).get_column(field).to_list()
            )
            if (normalized := _normalize_text(value)) is not None
        }
        if not dup_values:
            continue
        for r in df.select(["row_number", field]).to_dicts():
            value = _normalize_text(r.get(field))
            if value is not None and value in dup_values:
                errors.append(
                    {
                        "row_number": int(r.get("row_number") or 0),
                        "field": field,
                        "message": f"Duplicate value for field {field}: {value} / 字段 {field} 重复值: {value}",
                        "value": value,
                        "type": SCHEMA_ERROR,
                    }
                )
    return errors


def build_conflict_errors(
    df: pl.DataFrame, field: str, conflict_values: Iterable[object], *, reason: str
) -> list[dict[str, Any]]:
    """
    Build conflict error list.
    构建冲突错误列表。

    Args:
        df: Input DataFrame (must contain row_number).
        df: 输入数据框（必须包含 row_number）。
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
    cv = {normalized for value in conflict_values if (normalized := _normalize_text(value)) is not None}
    if not cv or df.is_empty() or field not in df.columns:
        return []
    errors: list[dict[str, Any]] = []
    for r in df.select(["row_number", field]).to_dicts():
        value = _normalize_text(r.get(field))
        if value is not None and value in cv:
            errors.append(
                {
                    "row_number": int(r.get("row_number") or 0),
                    "field": field,
                    "message": f"Conflict: {reason}; {field}={value} / 冲突：{reason}；{field}={value}",
                    "value": value,
                    "type": "db_conflict",
                }
            )
    return errors
