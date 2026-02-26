"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_template_contracts.py
@DateTime: 2026-02-26
@Docs: Tests for built-in template contract presets.
内置模板契约预设测试。
"""

from fastapi_import_export.template_contracts import BOOK_STATUS_ENUM, BOOK_TEMPLATE_COLUMNS, get_book_template_contract


def test_book_contract_contains_required_columns() -> None:
    contract = get_book_template_contract()
    fields = {item["field"] for item in contract["columns"]}
    assert "isbn" in fields
    assert "title" in fields
    assert "status" in fields


def test_book_status_enum_aliases() -> None:
    assert BOOK_STATUS_ENUM["可借阅"] == "available"
    assert BOOK_STATUS_ENUM["不可借阅"] == "unavailable"


def test_book_template_columns_have_examples() -> None:
    assert BOOK_TEMPLATE_COLUMNS
    assert all(str(item.get("example") or "").strip() for item in BOOK_TEMPLATE_COLUMNS)
