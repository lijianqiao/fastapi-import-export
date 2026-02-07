"""
Core validation primitives (no business rules).
校验核心原语（不包含任何业务规则）。

This module intentionally does NOT include rules like IP/enum/regex checks.
It only provides:
- ErrorCollector: append standardized error items.
- RowContext: per-row helper to read values and emit errors.
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
            row_number (int): 行号。
            field (str | None): 字段名，默认值为 None。
            message (str): 错误消息。
            value (Any | None, optional): 相关值，默认值为 None。
            type (str | None, optional): 错误类型，默认值为 None。
            details (Any | None, optional): 详细信息，默认值为 None。
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
            field (str | None): 字段名，默认值为 None。
            message (str): 错误消息。
            value (Any | None, optional): 相关值，默认值为 None。
            type (str | None, optional): 错误类型，默认值为 None。
            details (Any | None, optional): 详细信息，默认值为 None。
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
            field (str): 字段名。

        Returns:
            str: 字符串值，默认值为空字符串。
        """
        v = self.row.get(field)
        if v is None:
            return ""
        return str(v).strip()
