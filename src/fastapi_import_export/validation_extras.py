"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: validation_extras.py
@DateTime: 2026-02-08
@Docs: Optional validation helpers with business-style rules.
可选校验扩展（偏业务规则）。

Optional validation helpers (business-ish rules).
可选校验扩展（包含 IP/枚举/正则 等规则）。

This module is optional by design. The core package does not require
projects to use these helpers.
本模块为可选扩展；核心库不要求业务使用这些规则。
"""

import ipaddress
import re
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi_import_export.error_codes import SCHEMA_ERROR
from fastapi_import_export.validation_core import ErrorCollector, RowContext


class RowValidator(RowContext):
    """Per-row helper to read values and emit errors.
    每行校验助手，用于读取值和发射错误。
    """

    def __init__(self, *, errors: list[dict[str, Any]], row_number: int, row: dict[str, Any]):
        """Initialize the validator.
        初始化校验助手。

        Args:
            errors: Error list for collecting validation errors.
                错误列表，用于存储校验错误。
            row_number: Row number for error location.
                当前行号，用于错误定位。
            row: Row data containing fields to validate.
                当前行数据，包含待校验字段。
        """
        super().__init__(collector=ErrorCollector(errors), row_number=int(row_number), row=row)

    def not_blank(self, field: str, message: str) -> None:
        """Check if the field is not blank.
        校验字段是否不为空。

        Args:
            field: Field name.
                字段名。
            message: Error message.
                错误消息。
        """
        v = self.get_str(field)
        if not v:
            self.add(field=field, message=message, type=SCHEMA_ERROR)

    def ip_address(self, field: str, message: str) -> None:
        """Check if the field is a valid IP address.
        校验字段是否为有效 IP 地址。

        Args:
            field: Field name.
                字段名。
            message: Error message.
                错误消息。
        """
        v = self.get_str(field)
        if not v:
            return
        try:
            ipaddress.ip_address(v)
        except Exception:
            self.add(field=field, message=message, value=v, type=SCHEMA_ERROR)

    def one_of(self, field: str, allowed: set[str], message_prefix: str) -> None:
        """Check if the field is one of the allowed values.
        校验字段是否为允许的值。

        Args:
            field: Field name.
                字段名。
            allowed: Allowed values.
                允许的值集合。
            message_prefix: Error message prefix.
                错误消息前缀。
        """
        v = self.get_str(field)
        if not v:
            return
        if v not in allowed:
            self.add(
                field=field,
                message=f"Value not allowed: {v} / {message_prefix}: {v}",
                value=v,
                type=SCHEMA_ERROR,
            )

    def regex(self, field: str, pattern: str, message: str) -> None:
        """Check if the field matches the regex pattern.
        校验字段是否匹配正则表达式。

        Args:
            field: Field name.
                字段名。
            pattern: Regex pattern.
                正则表达式模式。
            message: Error message.
                错误消息。
        """
        v = self.get_str(field)
        if not v:
            return
        if re.fullmatch(pattern, v) is None:
            self.add(field=field, message=message, value=v, type=SCHEMA_ERROR)

    def require_fields(self, fields: Iterable[str], message_prefix: str) -> None:
        """Check if the required fields are not blank.
        校验必填字段是否不为空。

        Args:
            fields: Required field names.
                必填字段名列表。
            message_prefix: Error message prefix.
                错误消息前缀。
        """
        for f in fields:
            if not self.get_str(f):
                self.add(
                    field=f,
                    message=f"Missing required field {f} / {message_prefix} {f}",
                    type=SCHEMA_ERROR,
                )

    def db_unique_conflict(
        self,
        *,
        field: str,
        deleted_map: dict[str, bool],
        allow_overwrite: bool,
        exists_message: str,
        deleted_message: str,
    ) -> None:
        """Check if the field value conflicts with the database unique constraint.
        校验字段值是否与数据库唯一约束冲突。

        Args:
            field: Field name.
                字段名。
            deleted_map: Deleted-value map (value -> deleted flag).
                已删除值映射，键为值，值为是否已删除。
            allow_overwrite: Whether overwrite is allowed.
                是否允许覆盖已删除值。
            exists_message: Message when value already exists.
                值已存在错误消息。
            deleted_message: Message when value is deleted.
                值已删除错误消息。
        """
        if allow_overwrite:
            return
        v = self.get_str(field)
        if not v:
            return
        deleted = deleted_map.get(v)
        if deleted is True:
            msg = deleted_message.format(value=v) if "{value}" in deleted_message else deleted_message
            self.add(
                field=field,
                message=f"DB unique conflict (deleted): {msg} / 数据库唯一冲突（已删除）：{msg}",
                value=v,
                type="db_conflict",
            )
        elif deleted is False:
            msg = exists_message.format(value=v) if "{value}" in exists_message else exists_message
            self.add(
                field=field,
                message=f"DB unique conflict: {msg} / 数据库唯一冲突：{msg}",
                value=v,
                type="db_conflict",
            )


def coerce_polars_types(
    df: Any,
    *,
    type_rules: dict[str, str],
    enum_aliases: dict[str, dict[str, Any]] | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Coerce Polars rows by simple type rules and collect row-level errors.
    基于简单类型规则转换 Polars 行数据，并收集行级错误。

    This helper is designed for validate-stage pre-checks, so type errors are
    returned before commit/persist.
    该助手用于 validate 阶段前置检查，让类型错误在 commit/persist 前返回。

    Supported rule values:
        - int / float / decimal / bool / date / datetime / str / enum
        支持规则值：int / float / decimal / bool / date / datetime / str / enum

    Args:
        df: Polars DataFrame with optional `row_number`.
            Polars DataFrame（可包含 `row_number` 列）。
        type_rules: Field -> rule mapping.
            字段到规则的映射。
        enum_aliases: Field -> alias map when rule is enum.
            当规则为 enum 时，字段到别名映射。

    Returns:
        tuple[Any, list[dict[str, Any]]]:
            - valid_df: Rows with successful coercion.
              valid_df：转换成功的行。
            - errors: Type errors with `type=type_error`.
              errors：类型错误列表（`type=type_error`）。
    """
    try:
        import polars as pl
    except Exception as exc:
        raise RuntimeError("polars is required for coerce_polars_types / coerce_polars_types 需要 polars") from exc

    if df is None or getattr(df, "is_empty", lambda: True)():
        return pl.DataFrame(), []

    enum_aliases = enum_aliases or {}
    rows = df.to_dicts()
    valid_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    truthy = {"1", "true", "yes", "y", "on"}
    falsy = {"0", "false", "no", "n", "off"}

    for row in rows:
        row_number = int(row.get("row_number") or 0)
        converted = dict(row)
        has_error = False
        for field, rule in type_rules.items():
            if field not in row:
                continue
            raw = row.get(field)
            text = "" if raw is None else str(raw).strip()
            if text == "":
                converted[field] = None
                continue
            rule_name = str(rule).strip().lower()
            try:
                if rule_name == "int":
                    converted[field] = int(text)
                elif rule_name == "float":
                    converted[field] = float(text)
                elif rule_name == "decimal":
                    converted[field] = Decimal(text)
                elif rule_name == "bool":
                    low = text.lower()
                    if low in truthy:
                        converted[field] = True
                    elif low in falsy:
                        converted[field] = False
                    else:
                        raise ValueError("invalid bool")
                elif rule_name == "date":
                    converted[field] = date.fromisoformat(text)
                elif rule_name == "datetime":
                    converted[field] = datetime.fromisoformat(text)
                elif rule_name == "str":
                    converted[field] = text
                elif rule_name == "enum":
                    aliases = enum_aliases.get(field, {})
                    converted[field] = aliases.get(text, aliases.get(text.lower(), text))
                else:
                    raise ValueError("unsupported rule")
            except Exception:
                errors.append(
                    {
                        "row_number": row_number,
                        "field": field,
                        "message": f"Invalid {rule_name} value: {text} / {field} 字段类型错误: {text}",
                        "type": "type_error",
                        "value": text,
                    }
                )
                has_error = True
        if not has_error:
            valid_rows.append(converted)

    return (pl.DataFrame(valid_rows) if valid_rows else pl.DataFrame()), errors


def drop_internal_columns(df: Any, *, internal_columns: Iterable[str] = ("row_number",)) -> Any:
    """Drop framework metadata columns before persistence.
    在持久化之前删除框架元字段列。

    Args:
        df: Input DataFrame.
            输入 DataFrame。
        internal_columns: Internal columns to remove.
            需要移除的内部列。

    Returns:
        Any: DataFrame without internal columns.
            删除内部列后的 DataFrame。
    """
    columns = set(getattr(df, "columns", []))
    to_drop = [name for name in internal_columns if name in columns]
    if not to_drop:
        return df
    return df.drop(to_drop)
