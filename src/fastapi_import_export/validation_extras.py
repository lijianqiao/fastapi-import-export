"""
Optional validation helpers (business-ish rules).
可选校验扩展（包含 IP/枚举/正则 等规则）。

This module is optional by design. The core package does not require
projects to use these helpers.
本模块为可选扩展；核心库不要求业务使用这些规则。
"""

import ipaddress
import re
from collections.abc import Iterable
from typing import Any

from fastapi_import_export.validation_core import ErrorCollector, RowContext


class RowValidator(RowContext):
    """Per-row helper to read values and emit errors.
    每行校验助手，用于读取值和发射错误。
    """

    def __init__(self, *, errors: list[dict[str, Any]], row_number: int, row: dict[str, Any]):
        """Initialize the validator.
        初始化校验助手。

        Args:
            errors (list[dict[str, Any]]): 错误列表，用于存储校验错误。
            row_number (int): 当前行号，用于错误定位。
            row (dict[str, Any]): 当前行数据，包含待校验字段。
        """
        super().__init__(collector=ErrorCollector(errors), row_number=int(row_number), row=row)

    def not_blank(self, field: str, message: str) -> None:
        """Check if the field is not blank.
        校验字段是否不为空。

        Args:
            field (str): 字段名。
            message (str): 错误消息。
        """
        v = self.get_str(field)
        if not v:
            self.add(field=field, message=message, type="required")

    def ip_address(self, field: str, message: str) -> None:
        """Check if the field is a valid IP address.
        校验字段是否为有效 IP 地址。

        Args:
            field (str): 字段名。
            message (str): 错误消息。
        """
        v = self.get_str(field)
        if not v:
            return
        try:
            ipaddress.ip_address(v)
        except Exception:
            self.add(field=field, message=message, value=v, type="format")

    def one_of(self, field: str, allowed: set[str], message_prefix: str) -> None:
        """Check if the field is one of the allowed values.
        校验字段是否为允许的值。

        Args:
            field (str): 字段名。
            allowed (set[str]): 允许的值集合。
            message_prefix (str): 错误消息前缀。
        """
        v = self.get_str(field)
        if not v:
            return
        if v not in allowed:
            self.add(field=field, message=f"{message_prefix}: {v}", value=v, type="enum")

    def regex(self, field: str, pattern: str, message: str) -> None:
        """Check if the field matches the regex pattern.
        校验字段是否匹配正则表达式。

        Args:
            field (str): 字段名。
            pattern (str): 正则表达式模式。
            message (str): 错误消息。
        """
        v = self.get_str(field)
        if not v:
            return
        if re.fullmatch(pattern, v) is None:
            self.add(field=field, message=message, value=v, type="format")

    def require_fields(self, fields: Iterable[str], message_prefix: str) -> None:
        """Check if the required fields are not blank.
        校验必填字段是否不为空。

        Args:
            fields (Iterable[str]): 必填字段名列表。
            message_prefix (str): 错误消息前缀。
        """
        for f in fields:
            if not self.get_str(f):
                self.add(field=f, message=f"{message_prefix} {f}", type="required")

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
            field (str): 字段名。
            deleted_map (dict[str, bool]): 已删除值映射，键为值，值为是否已删除。
            allow_overwrite (bool): 是否允许覆盖已删除值。
            exists_message (str): 值已存在错误消息。
            deleted_message (str): 值已删除错误消息。
        """
        if allow_overwrite:
            return
        v = self.get_str(field)
        if not v:
            return
        deleted = deleted_map.get(v)
        if deleted is True:
            msg = deleted_message.format(value=v) if "{value}" in deleted_message else deleted_message
            self.add(field=field, message=msg, value=v, type="db_conflict")
        elif deleted is False:
            msg = exists_message.format(value=v) if "{value}" in exists_message else exists_message
            self.add(field=field, message=msg, value=v, type="db_conflict")
