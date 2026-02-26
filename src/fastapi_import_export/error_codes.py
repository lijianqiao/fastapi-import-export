"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: error_codes.py
@DateTime: 2026-02-26
@Docs: Unified error code dictionary and normalization helpers.
统一错误码字典与归一化辅助。
"""

from typing import Any

SCHEMA_ERROR = "schema_error"
TYPE_ERROR = "type_error"
DB_CONFLICT = "db_conflict"

ERROR_CODE_DICT: dict[str, str] = {
    SCHEMA_ERROR: "Schema/contract validation error / 模板结构或业务规则错误",
    TYPE_ERROR: "Type conversion or parsing error / 类型转换或解析错误",
    DB_CONFLICT: "Database uniqueness/conflict error / 数据库唯一约束或冲突错误",
}

_SCHEMA_ALIASES = {
    "required",
    "format",
    "enum",
    "schema",
    "schema_error",
    "infile_duplicate",
}
_TYPE_ALIASES = {
    "type",
    "type_error",
}
_DB_ALIASES = {
    "db",
    "db_check",
    "db_conflict",
}


def normalize_error_type(error_type: str | None) -> str:
    """Normalize error type to one of unified error codes.
    将错误类型归一化为统一错误码之一。

    Args:
        error_type: Raw error type string.
            原始错误类型字符串。

    Returns:
        str: One of schema_error/type_error/db_conflict.
            统一错误码之一：schema_error/type_error/db_conflict。
    """
    normalized = str(error_type or "").strip().lower()
    if normalized in _TYPE_ALIASES:
        return TYPE_ERROR
    if normalized in _DB_ALIASES:
        return DB_CONFLICT
    if normalized in _SCHEMA_ALIASES:
        return SCHEMA_ERROR
    return SCHEMA_ERROR


def normalize_error_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single error item to unified error code type.
    将单条错误项归一化为统一错误码类型。

    Args:
        item: Raw error item.
            原始错误项。

    Returns:
        dict[str, Any]: Normalized error item.
            归一化后的错误项。
    """
    normalized = dict(item)
    normalized["type"] = normalize_error_type(str(item.get("type") or ""))
    return normalized
