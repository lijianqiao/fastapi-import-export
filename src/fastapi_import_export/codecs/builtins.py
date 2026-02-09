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
    if value is None:
        return True
    return not str(value).strip()


class EnumCodec(Codec[Enum]):
    """Codec for Enum values.
    枚举类型编解码器。
    """

    def __init__(self, enum_type: type[TEnum] | Iterable[object] | Mapping[object, object]):
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
        # Try case-insensitive match
        raw_lower = raw.lower()
        for member in self._members:
            if raw_lower == member.name.lower() or raw_lower == str(member.value).lower():
                return member
        raise ValueError(f"Invalid enum value: {raw}")

    def format(self, value: Enum | None) -> str:
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
        if _blank(value):
            return None
        return date.fromisoformat(str(value).strip())

    def format(self, value: date | None) -> str:
        if value is None:
            return ""
        return value.isoformat()


class DatetimeCodec(Codec[datetime]):
    """Codec for datetime values.
    日期时间类型编解码器。
    """

    def parse(self, value: str | None) -> datetime | None:
        if _blank(value):
            return None
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        return datetime.fromisoformat(text)

    def format(self, value: datetime | None) -> str:
        if value is None:
            return ""
        return value.isoformat()


class DecimalCodec(Codec[Decimal]):
    """Codec for Decimal values.
    Decimal 类型编解码器。
    """

    def parse(self, value: str | None) -> Decimal | None:
        if _blank(value):
            return None
        return Decimal(str(value).strip())

    def format(self, value: Decimal | None) -> str:
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
        if _blank(value):
            return None
        raw = str(value).strip().lower()
        if raw in self._truthy:
            return True
        if raw in self._falsy:
            return False
        raise ValueError(f"Invalid bool value: {value}")

    def format(self, value: bool | None) -> str:
        if value is None:
            return ""
        return "true" if value else "false"
