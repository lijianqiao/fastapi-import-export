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
        """
        ...

    def format(self, value: T | None) -> str:
        """Format a typed value into a string.
        将类型化的值格式化为字符串。
        """
        ...
