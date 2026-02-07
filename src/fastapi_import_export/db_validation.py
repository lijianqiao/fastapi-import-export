"""
Database-focused validation helpers for import workflow.
导入流程的“数据库校验”通用辅助（不包含业务格式校验）。

Design Goals:
- No assumptions about ORM/table structure: The business side provides `db_check_fn` to query the database.
- This library is only responsible for: mapping "conflicting results" back to `row_number` and generating a unified error structure.
- Applicable to all "DB-based checks" such as soft deletion, unique keys, and foreign key existence.

设计目标 / Goals:
- 不假设 ORM/表结构：由业务侧提供 db_check_fn 来查询数据库。
- 本库只负责：把“冲突结果”映射回 row_number，并生成统一错误结构。
- 适用于软删除/唯一键/外键存在性等一切“基于 DB 的校验”。
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

import polars as pl

KeyTuple = tuple[str, ...]


class DbCheckFn(Protocol):
    async def __call__(
        self,
        db: Any,
        keys: list[KeyTuple],
        *,
        allow_overwrite: bool = False,
    ) -> dict[KeyTuple, dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class DbCheckSpec:
    """数据库校验规范（告诉通用库“按哪些列拼 key”，以及如何查库与报错）。

    Attributes:
        key_fields (list[str]): 用于拼 key 的列名列表。
        check_fn (DbCheckFn): 业务侧实现的查库函数。
        field (str | None, optional): 校验失败时的字段名，默认值为 None。
        message (str, optional): 校验失败时的默认错误消息，默认值为 "数据库校验失败"。
        type (str, optional): 校验类型，默认值为 "db_check"。
    """

    key_fields: list[str]
    check_fn: DbCheckFn
    field: str | None = None
    message: str = "数据库校验失败"
    type: str = "db_check"


def build_key_to_row_numbers(df: pl.DataFrame, key_fields: Iterable[str]) -> dict[KeyTuple, list[int]]:
    """Build mapping: key(tuple of str) -> row_number list.

    构建映射：key（字符串元组） -> 行号列表。

    Args:
        df (pl.DataFrame): 包含校验数据的 DataFrame，必须包含 "row_number" 列。
        key_fields (Iterable[str]): 用于拼 key 的列名列表。

    Returns:
        dict[KeyTuple, list[int]]: 映射：key（字符串元组） -> 行号列表。
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
    """Convert db conflict map to error list with row_number.

    将数据库冲突映射转换为包含 row_number 的错误列表。

    Args:
        key_to_row_numbers (dict[KeyTuple, list[int]]): 映射：key（字符串元组） -> 行号列表。
        conflicts (dict[KeyTuple, dict[str, Any]]): 映射：key（字符串元组） -> 冲突信息（包含 "message" 和可选的 "details"）。
        field (str | None): 校验失败时的字段名，默认值为 None。
        default_message (str): 校验失败时的默认错误消息，默认值为 "数据库校验失败"。
        type (str): 校验类型，默认值为 "db_check"。
        max_rows_per_key (int, optional): 每个 key 最多返回的 row_number 数量，默认值为 50。

    Returns:
        list[dict[str, Any]]: 包含 row_number、field、message、type、value（可选）和 details（可选）的错误列表。
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
    """Run database checks and return error list.

    执行数据库校验并返回错误列表。

    Args:
        db (Any): 数据库连接对象，由业务侧提供。
        df (pl.DataFrame): 包含校验数据的 DataFrame，必须包含 "row_number" 列。
        specs (list[DbCheckSpec]): 数据库校验规范列表。
        allow_overwrite (bool, optional): 是否允许覆盖已存在数据，默认值为 False。

    Returns:
        list[dict[str, Any]]: 包含 row_number、field、message、type、value（可选）和 details（可选）的错误列表。
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
