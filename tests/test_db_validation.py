"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_db_validation.py
@DateTime: 2026-02-08
@Docs: Tests for db_validation.py and db_validation_polars.py modules.
db_validation.py 与 db_validation_polars.py 模块测试。
"""

from typing import Any

import polars as pl
import pytest

from fastapi_import_export.db_validation import DbCheckSpec
from fastapi_import_export.db_validation_polars import (
    build_db_conflict_errors,
    build_key_to_row_numbers,
    run_db_checks,
)


class TestBuildKeyToRowNumbers:
    """Tests for build_key_to_row_numbers.
    build_key_to_row_numbers 测试。
    """

    def test_single_key_field(self) -> None:
        """Single key field mapping / 单字段 key 映射。"""
        df = pl.DataFrame({"row_number": [1, 2, 3], "email": ["a", "b", "a"]})
        result = build_key_to_row_numbers(df, ["email"])
        assert ("a",) in result
        assert result[("a",)] == [1, 3]
        assert result[("b",)] == [2]

    def test_composite_key(self) -> None:
        """Composite key mapping / 复合 key 映射。"""
        df = pl.DataFrame(
            {
                "row_number": [1, 2],
                "name": ["alice", "bob"],
                "email": ["a@b.com", "b@c.com"],
            }
        )
        result = build_key_to_row_numbers(df, ["name", "email"])
        assert ("alice", "a@b.com") in result

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame returns empty / 空 DataFrame 返回空字典。"""
        df = pl.DataFrame({"row_number": [], "email": []}).cast({"row_number": pl.Int64, "email": pl.Utf8})
        result = build_key_to_row_numbers(df, ["email"])
        assert result == {}

    def test_missing_row_number_column(self) -> None:
        """Missing row_number returns empty / 缺少 row_number 列返回空字典。"""
        df = pl.DataFrame({"email": ["a@b.com"]})
        result = build_key_to_row_numbers(df, ["email"])
        assert result == {}

    def test_empty_key_skipped(self) -> None:
        """Empty key values are skipped / 空 key 值被跳过。"""
        df = pl.DataFrame({"row_number": [1, 2], "email": ["a@b.com", ""]})
        result = build_key_to_row_numbers(df, ["email"])
        assert ("",) not in result

    def test_empty_key_fields_list(self) -> None:
        """Empty key_fields returns empty / 空 key_fields 返回空字典。"""
        df = pl.DataFrame({"row_number": [1], "email": ["a"]})
        result = build_key_to_row_numbers(df, [])
        assert result == {}


class TestBuildDbConflictErrors:
    """Tests for build_db_conflict_errors.
    build_db_conflict_errors 测试。
    """

    def test_correct_association(self) -> None:
        """Associate row numbers with conflicts / 正确关联行号与冲突。"""
        key_to_rows = {("a",): [1, 3], ("b",): [2]}
        conflicts = {("a",): {"message": "exists"}}
        errors = build_db_conflict_errors(
            key_to_row_numbers=key_to_rows,
            conflicts=conflicts,
            field="email",
            default_message="conflict",
            type="db_check",
        )
        assert len(errors) == 2
        assert all(e["field"] == "email" for e in errors)

    def test_max_rows_per_key_truncation(self) -> None:
        """Truncate row numbers per key / 截断每个 key 的行号。"""
        key_to_rows = {("a",): list(range(1, 101))}
        conflicts = {("a",): {"message": "exists"}}
        errors = build_db_conflict_errors(
            key_to_row_numbers=key_to_rows,
            conflicts=conflicts,
            field="email",
            default_message="conflict",
            type="db_check",
            max_rows_per_key=5,
        )
        assert len(errors) == 5

    def test_no_conflicts(self) -> None:
        """No conflicts returns empty / 无冲突返回空列表。"""
        errors = build_db_conflict_errors(
            key_to_row_numbers={("a",): [1]},
            conflicts={},
            field="email",
            default_message="conflict",
            type="db_check",
        )
        assert len(errors) == 0


class TestRunDbChecks:
    """Tests for run_db_checks.
    run_db_checks 测试。
    """

    @pytest.mark.asyncio
    async def test_multiple_specs_aggregated(self) -> None:
        """Multiple specs aggregate errors / 多个 spec 汇总错误。"""
        df = pl.DataFrame({"row_number": [1, 2], "email": ["a@b.com", "c@d.com"], "name": ["alice", "bob"]})

        async def check_email(db: Any, keys: list, *, allow_overwrite: bool = False) -> dict:
            return {("a@b.com",): {"message": "email exists"}}

        async def check_name(db: Any, keys: list, *, allow_overwrite: bool = False) -> dict:
            return {("bob",): {"message": "name exists"}}

        specs = [
            DbCheckSpec(key_fields=["email"], check_fn=check_email, field="email"),
            DbCheckSpec(key_fields=["name"], check_fn=check_name, field="name"),
        ]
        errors = await run_db_checks(db=None, df=df, specs=specs, allow_overwrite=False)
        assert len(errors) == 2

    @pytest.mark.asyncio
    async def test_allow_overwrite_passed_through(self) -> None:
        """allow_overwrite is passed to check_fn / allow_overwrite 透传到 check_fn。"""
        df = pl.DataFrame({"row_number": [1], "email": ["a@b.com"]})
        called_with: dict[str, Any] = {}

        async def check_fn(db: Any, keys: list, *, allow_overwrite: bool = False) -> dict:
            called_with["allow_overwrite"] = allow_overwrite
            return {}

        specs = [DbCheckSpec(key_fields=["email"], check_fn=check_fn)]
        await run_db_checks(db=None, df=df, specs=specs, allow_overwrite=True)
        assert called_with["allow_overwrite"] is True

    @pytest.mark.asyncio
    async def test_no_conflicts_empty_result(self) -> None:
        """No conflicts returns empty list / 无冲突返回空列表。"""
        df = pl.DataFrame({"row_number": [1], "email": ["a@b.com"]})

        async def check_fn(db: Any, keys: list, *, allow_overwrite: bool = False) -> dict:
            return {}

        specs = [DbCheckSpec(key_fields=["email"], check_fn=check_fn)]
        errors = await run_db_checks(db=None, df=df, specs=specs)
        assert errors == []
