"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: db_validation_polars.py
@DateTime: 2026-02-08
@Docs: Polars-backed DB validation helpers.
基于 Polars 的数据库校验辅助。
"""

from collections.abc import Iterable
from typing import Any

import polars as pl

from fastapi_import_export.db_validation import DbCheckSpec, KeyTuple


def build_key_to_row_numbers(df: pl.DataFrame, key_fields: Iterable[str]) -> dict[KeyTuple, list[int]]:
    """
    Build mapping: key tuple -> row_number list.
    构建映射：key 元组 -> 行号列表。

    Args:
        df: DataFrame with row_number.
        df: 包含 row_number 的数据框。
        key_fields: Key fields.
        key_fields: key 字段列表。

    Returns:
        dict[KeyTuple, list[int]]: Mapping from key to row numbers.
        dict[KeyTuple, list[int]]: key 到行号映射。
    """
    fields = list(key_fields)
    if not fields:
        return {}
    if df.is_empty() or "row_number" not in df.columns:
        return {}
    for f in fields:
        if f not in df.columns:
            return {}

    key_to_rows: dict[KeyTuple, list[int]] = {}
    rows = df.select(["row_number", *fields]).to_dicts()
    for r in rows:
        row_number = int(r.get("row_number") or 0)
        key = tuple(str(r.get(f) or "").strip() for f in fields)
        if any(not part for part in key):
            continue
        key_to_rows.setdefault(key, []).append(row_number)
    return key_to_rows


def build_db_conflict_errors(
    *,
    key_to_row_numbers: dict[KeyTuple, list[int]],
    conflicts: dict[KeyTuple, dict[str, Any]],
    field: str | None,
    default_message: str,
    type: str,
    max_rows_per_key: int = 50,
) -> list[dict[str, Any]]:
    """
    Convert db conflict map to error list with row_number.
    将数据库冲突映射转换为包含 row_number 的错误列表。

    Args:
        key_to_row_numbers: key -> row_number mapping.
        key_to_row_numbers: key -> 行号映射。
        conflicts: key -> conflict info mapping.
        conflicts: key -> 冲突信息映射。
        field: Field name.
        field: 字段名。
        default_message: Default message.
        default_message: 默认错误消息。
        type: Error type.
        type: 错误类型。
        max_rows_per_key: Max row numbers per key.
        max_rows_per_key: 每个 key 最大返回行数。

    Returns:
        list[dict[str, Any]]: Error list.
        list[dict[str, Any]]: 错误列表。
    """
    errors: list[dict[str, Any]] = []
    for key, info in conflicts.items():
        row_numbers = key_to_row_numbers.get(key, [])
        msg = str(info.get("message") or default_message)
        details = info.get("details")
        value = info.get("value") or info.get("values") or key
        for rn in row_numbers[:max_rows_per_key]:
            item: dict[str, Any] = {"row_number": int(rn), "field": field, "message": msg, "type": type}
            item["value"] = value
            if details is not None:
                item["details"] = details
            errors.append(item)
    return errors


async def run_db_checks(
    *,
    db: Any,
    df: pl.DataFrame,
    specs: list[DbCheckSpec],
    allow_overwrite: bool = False,
) -> list[dict[str, Any]]:
    """
    Run database checks and return error list.
    执行数据库校验并返回错误列表。

    Args:
        db: Database connection.
        db: 数据库连接对象。
        df: DataFrame with row_number.
        df: 包含 row_number 的数据框。
        specs: Db check specs.
        specs: 数据库校验规范列表。
        allow_overwrite: Allow overwrite flag.
        allow_overwrite: 是否允许覆盖。

    Returns:
        list[dict[str, Any]]: Error list.
        list[dict[str, Any]]: 错误列表。
    """
    all_errors: list[dict[str, Any]] = []
    for spec in specs:
        key_to_rows = build_key_to_row_numbers(df, spec.key_fields)
        keys = list(key_to_rows.keys())
        if not keys:
            continue

        conflicts = await spec.check_fn(db, keys, allow_overwrite=allow_overwrite)
        if not conflicts:
            continue

        all_errors.extend(
            build_db_conflict_errors(
                key_to_row_numbers=key_to_rows,
                conflicts=conflicts,
                field=spec.field or (spec.key_fields[0] if spec.key_fields else None),
                default_message=spec.message,
                type=spec.type,
            )
        )
    return all_errors
