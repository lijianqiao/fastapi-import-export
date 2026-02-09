"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: builtins.py
@DateTime: 2026-02-09
@Docs: Built-in codecs for common types.
内置常用类型编解码器。
"""

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TypeVar

from fastapi_import_export.codecs.base import Codec

TEnum = TypeVar("TEnum", bound=Enum)


def _blank(value: object | None) -> bool:
    """Return True if a value is blank (None or all-whitespace).
    如果值为空（None 或全为空白）则返回 True。

    Args:
        value: Any value to test.
            要检测的任意值。

    Returns:
        bool: True when blank, otherwise False.
            如果为空则为 True，否则为 False。
    """
    if value is None:
        return True
    return not str(value).strip()


class EnumCodec(Codec[Enum]):
    """Codec for Enum values.
    枚举类型编解码器。
    """

    def __init__(self, enum_type: type[TEnum] | Iterable[object] | Mapping[object, object]):
        """Initialize EnumCodec with an enum type, iterable of choices, or mapping.
        使用枚举类型、选项迭代器或映射初始化 EnumCodec。

        Args:
            enum_type: The enum type, iterable of choices, or mapping to use for parsing and formatting.
                用于解析和格式化的枚举类型、选项迭代器或映射。
        """
        self._enum_type = enum_type
        self._members: list[Enum] | None = None
        self._choices: list[str] | None = None
        self._mapping: dict[str, object] | None = None
        self._mapping_lower: dict[str, object] | None = None
        self._reverse_mapping: dict[object, str] | None = None

        if isinstance(enum_type, Mapping):
            mapping: dict[str, object] = {}
            mapping_lower: dict[str, object] = {}
            reverse: dict[object, str] = {}
            for key, value in enum_type.items():
                key_text = str(key)
                mapping[key_text] = value
                key_lower = key_text.lower()
                mapping_lower.setdefault(key_lower, value)
                try:
                    reverse.setdefault(value, key_text)
                except TypeError:
                    pass
            self._mapping = mapping
            self._mapping_lower = mapping_lower
            self._reverse_mapping = reverse
            return

        if isinstance(enum_type, type) and issubclass(enum_type, Enum):
            self._members = list(enum_type)
        else:
            self._choices = [str(v) for v in enum_type]

    def parse(self, value: str | None) -> Enum | None:
        """Parse a string value into an Enum member or mapped value.
        将字符串值解析为枚举成员或映射值。

        Args:
            value: The string value to parse.
                要解析的字符串值。
        Returns:
            The corresponding Enum member or mapped value, or None if the input is blank.
                对应的枚举成员或映射值，如果输入为空则返回 None。
        Raises:
            ValueError: If the input value cannot be parsed into a valid Enum member or mapped value.
                如果输入值无法解析为有效的枚举成员或映射值，则抛出 ValueError。
        """
        if _blank(value):
            return None
        raw = str(value).strip()
        if self._mapping is not None:
            if raw in self._mapping:
                return self._mapping[raw]  # type: ignore[return-value]
            raw_lower = raw.lower()
            if self._mapping_lower is not None and raw_lower in self._mapping_lower:
                return self._mapping_lower[raw_lower]  # type: ignore[return-value]
            raise ValueError(f"Invalid enum value: {raw}")
        if self._members is None:
            if self._choices is not None and raw in self._choices:
                return raw  # type: ignore[return-value]
            raise ValueError(f"Invalid enum value: {raw}")
        for member in self._members:
            if raw == member.name or raw == str(member.value):
                return member
        # Try case-insensitive match / 尝试不区分大小写匹配
        raw_lower = raw.lower()
        for member in self._members:
            if raw_lower == member.name.lower() or raw_lower == str(member.value).lower():
                return member
        raise ValueError(f"Invalid enum value: {raw}")

    def format(self, value: Enum | None) -> str:
        """Format an Enum member or mapped value into a string.
        将枚举成员或映射值格式化为字符串。

        Args:
            value: The Enum member or mapped value to format.
                要格式化的枚举成员或映射值。
        Returns:
            The formatted string representation of the value, or an empty string if the value is None.
                值的格式化字符串表示，如果值为 None 则返回空字符串。
        """
        if value is None:
            return ""
        if self._reverse_mapping is not None:
            try:
                mapped = self._reverse_mapping.get(value)
            except TypeError:
                mapped = None
            if mapped is not None:
                return mapped
        if isinstance(value, Enum):
            return str(value.value)
        return str(value)


class DateCodec(Codec[date]):
    """Codec for date values.
    日期类型编解码器。
    """

    def parse(self, value: str | None) -> date | None:
        """Parse a string value into a date.
        将字符串值解析为日期。

        Args:
            value: The string value to parse.
                要解析的字符串值。
        Returns:
            The corresponding date, or None if the input is blank.
                对应的日期，如果输入为空则返回 None。
        """
        if _blank(value):
            return None
        return date.fromisoformat(str(value).strip())

    def format(self, value: date | None) -> str:
        """Format a date into a string.
        将日期格式化为字符串。

        Args:
            value: The date to format.
                要格式化的日期。
        Returns:
                The formatted string representation of the date, or an empty string if the value is None.
                日期的格式化字符串表示，如果值为 None 则返回空字符串。
        """
        if value is None:
            return ""
        return value.isoformat()


class DatetimeCodec(Codec[datetime]):
    """Codec for datetime values.
    日期时间类型编解码器。
    """

    def parse(self, value: str | None) -> datetime | None:
        """Parse a string value into a datetime.
        将字符串值解析为日期时间。

        Args:
            value: The string value to parse.
                要解析的字符串值。
        Returns:
            The corresponding datetime, or None if the input is blank.
                对应的日期时间，如果输入为空则返回 None。
        """
        if _blank(value):
            return None
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        return datetime.fromisoformat(text)

    def format(self, value: datetime | None) -> str:
        """Format a datetime into a string.
        将日期时间格式化为字符串。

        Args:
            value: The datetime to format.
                要格式化的日期时间。
        Returns:
            The formatted string representation of the datetime, or an empty string if the value is None.
                日期时间的格式化字符串表示，如果值为 None 则返回空字符串。
        """
        if value is None:
            return ""
        return value.isoformat()


class DecimalCodec(Codec[Decimal]):
    """Codec for Decimal values.
    Decimal 类型编解码器。
    """

    def parse(self, value: str | None) -> Decimal | None:
        """Parse a string value into a Decimal.
        将字符串值解析为 Decimal。

        Args:
            value: The string value to parse.
                要解析的字符串值。
        Returns:
            The corresponding Decimal, or None if the input is blank.
                对应的 Decimal，如果输入为空则返回 None。
        """
        if _blank(value):
            return None
        return Decimal(str(value).strip())

    def format(self, value: Decimal | None) -> str:
        """Format a Decimal into a string.
        将 Decimal 格式化为字符串。

        Args:
            value: The Decimal to format.
                要格式化的 Decimal。
        Returns:
            The formatted string representation of the Decimal, or an empty string if the value is None.
                Decimal 的格式化字符串表示，如果值为 None 则返回空字符串。
        """
        if value is None:
            return ""
        if not value.is_finite():
            return str(value)
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < 0:
            return format(value, "f").rstrip("0").rstrip(".")
        return str(value)


class BoolCodec(Codec[bool]):
    """Codec for bool values.
    布尔类型编解码器。
    """

    _truthy = {"1", "true", "yes", "y", "t", "on"}
    _falsy = {"0", "false", "no", "n", "f", "off"}

    def parse(self, value: str | None) -> bool | None:
        """Parse a string value into a bool.
        将字符串值解析为布尔值。

        Args:
            value: The string value to parse.
                要解析的字符串值。
        Returns:
            The corresponding bool, or None if the input is blank.
                对应的布尔值，如果输入为空则返回 None。
        """
        if _blank(value):
            return None
        raw = str(value).strip().lower()
        if raw in self._truthy:
            return True
        if raw in self._falsy:
            return False
        raise ValueError(f"Invalid bool value: {value}")

    def format(self, value: bool | None) -> str:
        """Format a bool into a string.
        将布尔值格式化为字符串。

        Args:
            value: The bool to format.
                要格式化的布尔值。
        Returns:
            The formatted string representation of the bool, or an empty string if the value is None.
                布尔值的格式化字符串表示，如果值为 None 则返回空字符串。
        """
        if value is None:
            return ""
        return "true" if value else "false"
