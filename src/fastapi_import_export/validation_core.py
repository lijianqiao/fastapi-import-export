"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: validation_core.py
@DateTime: 2026-02-08
@Docs: Core validation primitives without business rules.
校验核心原语（不包含业务规则）。

Core validation primitives (no business rules).
校验核心原语（不包含任何业务规则）。

This module intentionally does NOT include rules like IP/enum/regex checks.
本模块刻意不包含 IP/枚举/正则 等规则。

It only provides:
仅提供如下内容：
- ErrorCollector: append standardized error items.
    ErrorCollector：添加标准化错误项。
- RowContext: per-row helper to read values and emit errors.
    RowContext：行级读取与错误发射辅助。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ErrorCollector:
    """Collect errors from row validations.
    从行校验中收集错误。
    """

    errors: list[dict[str, Any]]

    def add(
        self,
        *,
        row_number: int,
        field: str | None,
        message: str,
        value: Any | None = None,
        type: str | None = None,
        details: Any | None = None,
    ) -> None:
        """Add an error item.
        添加一个错误项。

        Args:
            row_number: Row number.
                行号。
            field: Field name (optional).
                字段名（可选，默认值为 None）。
            message: Error message.
                错误消息。
            value: Related value (optional).
                相关值（可选，默认值为 None）。
            type: Error type (optional).
                错误类型（可选，默认值为 None）。
            details: Extra details (optional).
                详细信息（可选，默认值为 None）。
        """
        item: dict[str, Any] = {"row_number": int(row_number), "field": field, "message": message}
        if value is not None:
            item["value"] = value
        if type is not None:
            item["type"] = type
        if details is not None:
            item["details"] = details
        self.errors.append(item)


@dataclass(slots=True)
class RowContext:
    """Per-row helper to read values and emit errors.
    每行校验助手，用于读取值和发射错误。
    """

    collector: ErrorCollector
    row_number: int
    row: Mapping[str, Any]

    def add(
        self,
        *,
        field: str | None,
        message: str,
        value: Any | None = None,
        type: str | None = None,
        details: Any | None = None,
    ) -> None:
        """Add an error item.
        添加一个错误项。

        Args:
            field: Field name (optional).
                字段名（可选，默认值为 None）。
            message: Error message.
                错误消息。
            value: Related value (optional).
                相关值（可选，默认值为 None）。
            type: Error type (optional).
                错误类型（可选，默认值为 None）。
            details: Extra details (optional).
                详细信息（可选，默认值为 None）。
        """
        self.collector.add(
            row_number=self.row_number,
            field=field,
            message=message,
            value=value,
            type=type,
            details=details,
        )

    def get_str(self, field: str) -> str:
        """Get a string value from the row.
        从行中获取字符串值。

        Args:
            field: Field name.
                字段名。

        Returns:
            str: String value (empty string when missing).
                字符串值（缺失时返回空字符串）。
        """
        v = self.row.get(field)
        if v is None:
            return ""
        return str(v).strip()
