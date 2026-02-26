"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_error_codes.py
@DateTime: 2026-02-26
@Docs: Tests for unified error code dictionary and normalization.
统一错误码字典与归一化测试。
"""

from fastapi_import_export.error_codes import (
    DB_CONFLICT,
    ERROR_CODE_DICT,
    SCHEMA_ERROR,
    TYPE_ERROR,
    normalize_error_item,
    normalize_error_type,
)


def test_error_code_dict_keys() -> None:
    assert SCHEMA_ERROR in ERROR_CODE_DICT
    assert TYPE_ERROR in ERROR_CODE_DICT
    assert DB_CONFLICT in ERROR_CODE_DICT


def test_normalize_error_type_schema_alias() -> None:
    assert normalize_error_type("required") == SCHEMA_ERROR
    assert normalize_error_type("infile_duplicate") == SCHEMA_ERROR


def test_normalize_error_type_type_alias() -> None:
    assert normalize_error_type("type_error") == TYPE_ERROR


def test_normalize_error_type_db_alias() -> None:
    assert normalize_error_type("db_check") == DB_CONFLICT


def test_normalize_error_item_sets_type() -> None:
    raw = {"row_number": 1, "field": "isbn", "message": "bad", "type": "enum"}
    normalized = normalize_error_item(raw)
    assert normalized["type"] == SCHEMA_ERROR
