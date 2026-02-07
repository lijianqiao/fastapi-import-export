"""Validation helpers.

通用校验辅助（默认不包含业务规则）。
"""

from collections.abc import Iterable
from typing import Any

import polars as pl


def collect_infile_duplicates(df: pl.DataFrame, unique_fields: Iterable[str]) -> list[dict[str, Any]]:
    """
    收集数据框中指定字段的重复值。

    Args:
        df (pl.DataFrame): 输入数据框，必须包含 "row_number" 列。
        unique_fields (Iterable[str]): 要检查重复值的字段列表。

    Returns:
        list[dict[str, Any]]: 包含重复值错误信息的列表，每个元素为一个字典，包含 "row_number"、"field"、"message"、"value" 和 "type" 键。
    """
    errors: list[dict[str, Any]] = []
    if df.is_empty():
        return errors
    cols = set(df.columns)
    for field in unique_fields:
        if field not in cols:
            continue
        # 分组统计，找出重复值
        dup_values = set(
            df.group_by(field).agg(pl.len().alias("count")).filter(pl.col("count") > 1).get_column(field).to_list()
        )
        if not dup_values:
            continue
        for r in df.select(["row_number", field]).to_dicts():
            value = str(r.get(field) or "")
            if value and value in dup_values:
                errors.append(
                    {
                        "row_number": int(r.get("row_number") or 0),
                        "field": field,
                        "message": f"字段 {field} 重复值: {value}",
                        "value": value,
                        "type": "infile_duplicate",
                    }
                )
    return errors


def build_conflict_errors(
    df: pl.DataFrame, field: str, conflict_values: Iterable[str], *, reason: str
) -> list[dict[str, Any]]:
    """
    构建数据库冲突错误信息。

    Args:
        df (pl.DataFrame): 输入数据框，必须包含 "row_number" 列。
        field (str): 冲突字段名。
        conflict_values (Iterable[str]): 冲突值列表。
        reason (str): 冲突原因描述。

    Returns:
        list[dict[str, Any]]: 包含冲突错误信息的列表，每个元素为一个字典，包含 "row_number"、"field"、"message"、"value" 和 "type" 键。
    """
    cv = {v for v in conflict_values if str(v).strip()}
    if not cv or df.is_empty() or field not in df.columns:
        return []
    errors: list[dict[str, Any]] = []
    for r in df.select(["row_number", field]).to_dicts():
        value = str(r.get(field) or "")
        if value and value in cv:
            errors.append(
                {
                    "row_number": int(r.get("row_number") or 0),
                    "field": field,
                    "message": f"{reason}：{field}={value}",
                    "value": value,
                    "type": "db_conflict",
                }
            )
    return errors
