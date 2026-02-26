"""
Tests for db_validation.py and db_validation_polars.py modules.
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
    def test_single_key_field(self) -> None:
        df = pl.DataFrame({"row_number": [1, 2, 3], "email": ["a", "b", "a"]})
        result = build_key_to_row_numbers(df, ["email"])
        assert ("a",) in result
        assert result[("a",)] == [1, 3]
        assert result[("b",)] == [2]

    def test_composite_key(self) -> None:
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
        df = pl.DataFrame({"row_number": [], "email": []}).cast({"row_number": pl.Int64, "email": pl.Utf8})
        result = build_key_to_row_numbers(df, ["email"])
        assert result == {}

    def test_missing_row_number_column(self) -> None:
        df = pl.DataFrame({"email": ["a@b.com"]})
        result = build_key_to_row_numbers(df, ["email"])
        assert result == {}

    def test_empty_key_skipped(self) -> None:
        df = pl.DataFrame({"row_number": [1, 2], "email": ["a@b.com", ""]})
        result = build_key_to_row_numbers(df, ["email"])
        assert ("",) not in result

    def test_empty_key_fields_list(self) -> None:
        df = pl.DataFrame({"row_number": [1], "email": ["a"]})
        result = build_key_to_row_numbers(df, [])
        assert result == {}

    def test_falsy_values_are_preserved(self) -> None:
        df = pl.DataFrame(
            {
                "row_number": [1, 2, 3, 4],
                "port": [0, 0, 1, 1],
                "enabled": [False, False, True, True],
            }
        )
        result = build_key_to_row_numbers(df, ["port", "enabled"])
        assert ("0", "False") in result
        assert result[("0", "False")] == [1, 2]


class TestBuildDbConflictErrors:
    def test_correct_association(self) -> None:
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
        errors = build_db_conflict_errors(
            key_to_row_numbers={("a",): [1]},
            conflicts={},
            field="email",
            default_message="conflict",
            type="db_check",
        )
        assert len(errors) == 0


class TestRunDbChecks:
    @pytest.mark.asyncio
    async def test_multiple_specs_aggregated(self) -> None:
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
        df = pl.DataFrame({"row_number": [1], "email": ["a@b.com"]})

        async def check_fn(db: Any, keys: list, *, allow_overwrite: bool = False) -> dict:
            return {}

        specs = [DbCheckSpec(key_fields=["email"], check_fn=check_fn)]
        errors = await run_db_checks(db=None, df=df, specs=specs)
        assert errors == []

