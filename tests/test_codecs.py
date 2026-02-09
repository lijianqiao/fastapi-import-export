"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_codecs.py
@DateTime: 2026-02-09
@Docs: Tests for built-in codecs.
内置 codecs 测试。
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from fastapi_import_export.codecs import BoolCodec, DateCodec, DatetimeCodec, DecimalCodec, EnumCodec


class Status(Enum):
    NEW = "new"
    DONE = "done"


class ZhStatus(Enum):
    AVAILABLE = "\u53ef\u501f\u9605"
    UNAVAILABLE = "\u5df2\u4e0b\u67b6"


def test_enum_codec_parse_and_format() -> None:
    codec = EnumCodec(Status)
    assert codec.parse("new") == Status.NEW
    assert codec.parse("DONE") == Status.DONE
    assert codec.format(Status.NEW) == "new"


def test_enum_codec_chinese_values() -> None:
    codec = EnumCodec(ZhStatus)
    assert codec.parse("\u53ef\u501f\u9605") == ZhStatus.AVAILABLE
    assert codec.parse("\u5df2\u4e0b\u67b6") == ZhStatus.UNAVAILABLE
    assert codec.format(ZhStatus.AVAILABLE) == "\u53ef\u501f\u9605"


def test_enum_codec_custom_mapping() -> None:
    mapping = {
        "\u53ef\u501f\u9605": ZhStatus.AVAILABLE,
        "\u5df2\u4e0b\u67b6": ZhStatus.UNAVAILABLE,
    }
    codec = EnumCodec(mapping)
    assert codec.parse("\u53ef\u501f\u9605") == ZhStatus.AVAILABLE
    assert codec.parse("\u5df2\u4e0b\u67b6") == ZhStatus.UNAVAILABLE
    assert codec.format(ZhStatus.AVAILABLE) == "\u53ef\u501f\u9605"


def test_date_codec() -> None:
    codec = DateCodec()
    value = codec.parse("2026-02-09")
    assert value == date(2026, 2, 9)
    assert codec.format(value) == "2026-02-09"


def test_datetime_codec() -> None:
    codec = DatetimeCodec()
    value = codec.parse("2026-02-09T10:11:12")
    assert isinstance(value, datetime)
    assert codec.format(value).startswith("2026-02-09T10:11:12")


def test_decimal_codec() -> None:
    codec = DecimalCodec()
    value = codec.parse("12.340")
    assert value == Decimal("12.340")
    assert codec.format(value) == "12.34"


def test_bool_codec() -> None:
    codec = BoolCodec()
    assert codec.parse("yes") is True
    assert codec.parse("0") is False
    assert codec.format(True) == "true"
    assert codec.format(False) == "false"
