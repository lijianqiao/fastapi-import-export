"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2026-02-09
@Docs: Codec protocol for parsing/formatting field values.
字段值编解码器协议。
"""

from typing import Protocol, TypeVar

T = TypeVar("T")


class Codec(Protocol[T]):
    """Codec protocol for parsing and formatting values.
    用于解析与格式化值的协议。
    """

    def parse(self, value: str | None) -> T | None:
        """Parse a raw string into a typed value.
        将原始字符串解析为类型化的值。

        Args:
            value: The raw string value to parse.
                要解析的原始字符串值。
        Returns:
            The parsed value of type T, or None if the input is blank.
                解析后的类型化值，如果输入为空则返回 None。
        """
        ...

    def format(self, value: T | None) -> str:
        """Format a typed value into a string.
        将类型化的值格式化为字符串。

        Args:
            value: The typed value to format.
                要格式化的类型化值。
        Returns:
            The formatted string representation of the value, or an empty string if the value is None.
                值的格式化字符串表示，如果值为 None 则返回空字符串。
        """
        ...
