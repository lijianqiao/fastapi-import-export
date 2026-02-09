"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: rows.py
@DateTime: 2026-02-09
@Docs: Helpers to iterate rows without exposing Polars details.
行迭代辅助（隐藏 Polars 细节）。
"""

from collections.abc import Iterable, Iterator, Mapping
from typing import Any


def iter_rows(data: Any) -> Iterator[dict[str, Any]]:
    """Iterate rows as dictionaries.
    以字典形式迭代行。

    Args:
        data: Polars DataFrame, iterable of mappings, or mapping.
            Polars DataFrame、映射行可迭代对象或单个映射。
    """
    if _is_polars_df(data):
        yield from data.to_dicts()
        return
    if isinstance(data, Mapping):
        yield dict(data)
        return
    if isinstance(data, (str, bytes)):
        raise TypeError("rows must be iterable mappings / 行数据必须是可迭代的映射")
    if isinstance(data, Iterable):
        for row in data:
            yield dict(row)
        return
    raise TypeError("rows must be iterable mappings / 行数据必须是可迭代的映射")


def rows_to_dicts(data: Any) -> list[dict[str, Any]]:
    """Convert row data into a list of dictionaries.
    将行数据转换为字典列表。
    """
    return list(iter_rows(data))


def _is_polars_df(value: Any) -> bool:
    try:
        import polars as pl  # type: ignore
    except Exception:
        return False
    return isinstance(value, pl.DataFrame)
