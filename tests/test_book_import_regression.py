"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_book_import_regression.py
@DateTime: 2026-02-26
@Docs: Regression tests for book import scenario.
图书导入场景回归测试。
"""

from decimal import Decimal
from typing import Any

import polars as pl

from fastapi_import_export.error_codes import DB_CONFLICT, SCHEMA_ERROR, TYPE_ERROR, normalize_error_item
from fastapi_import_export.template_contracts import BOOK_STATUS_ENUM
from fastapi_import_export.validation_extras import coerce_polars_types, drop_internal_columns
from fastapi_import_export.validation_polars import collect_infile_duplicates


def _validate_books(df: pl.DataFrame) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
    """Validate book rows for regression coverage.
    为回归覆盖执行图书行校验。
    """
    typed_df, type_errors = coerce_polars_types(
        df,
        type_rules={
            "isbn": "str",
            "title": "str",
            "status": "enum",
            "published_at": "date",
            "price": "decimal",
            "stock": "int",
        },
        enum_aliases={"status": BOOK_STATUS_ENUM},
    )
    errors: list[dict[str, Any]] = [normalize_error_item(item) for item in type_errors]
    if typed_df.is_empty():
        return typed_df, errors

    for row in typed_df.to_dicts():
        row_number = int(row.get("row_number") or 0)
        isbn = str(row.get("isbn") or "").strip()
        title = str(row.get("title") or "").strip()
        stock = row.get("stock")
        price = row.get("price")
        if not isbn:
            errors.append(
                {
                    "row_number": row_number,
                    "field": "isbn",
                    "message": "ISBN is required / ISBN 必填",
                    "type": SCHEMA_ERROR,
                }
            )
        if not title:
            errors.append(
                {
                    "row_number": row_number,
                    "field": "title",
                    "message": "Title is required / 标题必填",
                    "type": SCHEMA_ERROR,
                }
            )
        if stock is not None and int(stock) < 0:
            errors.append(
                {
                    "row_number": row_number,
                    "field": "stock",
                    "message": "Stock must be >= 0 / 库存必须大于等于 0",
                    "type": SCHEMA_ERROR,
                }
            )
        if price is not None and Decimal(price) < Decimal("0"):
            errors.append(
                {
                    "row_number": row_number,
                    "field": "price",
                    "message": "Price must be >= 0 / 价格必须大于等于 0",
                    "type": SCHEMA_ERROR,
                }
            )

    dup_errors = [normalize_error_item(item) for item in collect_infile_duplicates(typed_df, ["isbn"])]
    errors.extend(dup_errors)
    error_rows = {int(item.get("row_number") or 0) for item in errors}
    if not typed_df.is_empty() and error_rows and "row_number" in typed_df.columns:
        typed_df = typed_df.filter(~pl.col("row_number").is_in(list(error_rows)))
    return typed_df, errors


def test_row_number_meta_field_can_be_dropped_before_persist() -> None:
    df = pl.DataFrame({"row_number": [1], "isbn": ["9787302511854"], "title": ["FastAPI in Action"]})
    clean_df = drop_internal_columns(df)
    assert "row_number" not in clean_df.columns


def test_chinese_status_alias_is_accepted() -> None:
    df = pl.DataFrame(
        {
            "row_number": [1],
            "isbn": ["9787302511854"],
            "title": ["FastAPI in Action"],
            "status": ["可借阅"],
            "published_at": ["2026-02-01"],
            "price": ["79.00"],
            "stock": ["10"],
        }
    )
    valid_df, errors = _validate_books(df)
    assert len(errors) == 0
    assert valid_df.height == 1
    assert valid_df.to_dicts()[0]["status"] == "available"


def test_invalid_date_is_type_error() -> None:
    df = pl.DataFrame(
        {
            "row_number": [1],
            "isbn": ["9787302511854"],
            "title": ["FastAPI in Action"],
            "status": ["可借阅"],
            "published_at": ["2026/02/01"],
        }
    )
    _, errors = _validate_books(df)
    assert any(item["type"] == TYPE_ERROR and item["field"] == "published_at" for item in errors)


def test_duplicate_isbn_is_schema_error() -> None:
    df = pl.DataFrame(
        {
            "row_number": [1, 2],
            "isbn": ["9787302511854", "9787302511854"],
            "title": ["Book A", "Book B"],
            "status": ["可借阅", "可借阅"],
        }
    )
    _, errors = _validate_books(df)
    assert any(item["type"] == SCHEMA_ERROR and item["field"] == "isbn" for item in errors)


def test_empty_and_boundary_values() -> None:
    df = pl.DataFrame(
        {
            "row_number": [1, 2],
            "isbn": ["", "9787302511854"],
            "title": ["", "Boundary Book"],
            "status": ["可借阅", "不可借阅"],
            "price": ["-1", "0"],
            "stock": ["-1", "0"],
        }
    )
    _, errors = _validate_books(df)
    assert any(item["type"] == SCHEMA_ERROR and item["field"] == "isbn" for item in errors)
    assert any(item["type"] == SCHEMA_ERROR and item["field"] == "title" for item in errors)
    assert any(item["type"] == SCHEMA_ERROR and item["field"] == "price" for item in errors)
    assert any(item["type"] == SCHEMA_ERROR and item["field"] == "stock" for item in errors)
    assert all(item["type"] in {SCHEMA_ERROR, TYPE_ERROR, DB_CONFLICT} for item in errors)
