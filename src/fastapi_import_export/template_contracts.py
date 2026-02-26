"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template_contracts.py
@DateTime: 2026-02-26
@Docs: Built-in template contract presets for common scenarios.
常见场景内置模板契约预设。
"""

from typing import Any

BOOK_STATUS_ENUM: dict[str, str] = {
    "可借阅": "available",
    "不可借阅": "unavailable",
}

BOOK_TEMPLATE_COLUMNS: list[dict[str, str]] = [
    {"column": "ISBN", "field": "isbn", "required": "yes", "example": "9787302511854"},
    {"column": "Title", "field": "title", "required": "yes", "example": "FastAPI in Action"},
    {"column": "Author", "field": "author", "required": "yes", "example": "Li Ming"},
    {"column": "Status", "field": "status", "required": "yes", "example": "可借阅"},
    {"column": "PublishedAt", "field": "published_at", "required": "no", "example": "2026-01-01"},
    {"column": "Price", "field": "price", "required": "no", "example": "79.00"},
    {"column": "Stock", "field": "stock", "required": "no", "example": "10"},
]


def get_book_template_contract() -> dict[str, Any]:
    """Return the built-in book import template contract.
    返回内置图书导入模板契约。

    Returns:
        dict[str, Any]: Contract payload including columns and status enum mapping.
            契约内容，包含列定义与状态枚举映射。
    """
    return {
        "name": "book_import",
        "columns": BOOK_TEMPLATE_COLUMNS,
        "status_enum": dict(BOOK_STATUS_ENUM),
    }
