"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_helpers_rows.py
@DateTime: 2026-02-09
@Docs: Tests for row helpers.
行辅助函数测试。
"""

import polars as pl

from fastapi_import_export.helpers import iter_rows, rows_to_dicts


def test_iter_rows_polars() -> None:
    df = pl.DataFrame({"a": [1], "b": ["x"]})
    rows = list(iter_rows(df))
    assert rows == [{"a": 1, "b": "x"}]


def test_iter_rows_mapping() -> None:
    rows = list(iter_rows({"a": 1}))
    assert rows == [{"a": 1}]


def test_rows_to_dicts_iterable() -> None:
    rows = rows_to_dicts([{"a": 1}, {"a": 2}])
    assert rows == [{"a": 1}, {"a": 2}]
