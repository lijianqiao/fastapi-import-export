"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_validation_polars.py
@DateTime: 2026/02/15 20:47:33
@Docs: Tests for Polars-backed validation helpers.
基于 Polars 的校验辅助测试。
"""

import polars as pl

from fastapi_import_export.error_codes import SCHEMA_ERROR
from fastapi_import_export.validation_polars import (
    build_conflict_errors,
    collect_infile_duplicates,
)


class TestCollectInfileDuplicates:
    def test_has_duplicates(self) -> None:
        df = pl.DataFrame(
            {
                "row_number": [1, 2, 3],
                "email": ["a@b.com", "a@b.com", "c@d.com"],
            }
        )
        errors = collect_infile_duplicates(df, ["email"])
        assert len(errors) == 2
        assert all(e["type"] == SCHEMA_ERROR for e in errors)

    def test_no_duplicates(self) -> None:
        df = pl.DataFrame(
            {
                "row_number": [1, 2],
                "email": ["a@b.com", "c@d.com"],
            }
        )
        errors = collect_infile_duplicates(df, ["email"])
        assert len(errors) == 0

    def test_empty_dataframe(self) -> None:
        df = pl.DataFrame({"row_number": [], "email": []}).cast({"row_number": pl.Int64, "email": pl.Utf8})
        errors = collect_infile_duplicates(df, ["email"])
        assert len(errors) == 0

    def test_field_not_present(self) -> None:
        df = pl.DataFrame({"row_number": [1], "name": ["alice"]})
        errors = collect_infile_duplicates(df, ["nonexistent"])
        assert len(errors) == 0

    def test_multiple_unique_fields(self) -> None:
        df = pl.DataFrame(
            {
                "row_number": [1, 2, 3],
                "email": ["a@b.com", "a@b.com", "c@d.com"],
                "name": ["alice", "bob", "alice"],
            }
        )
        errors = collect_infile_duplicates(df, ["email", "name"])
        email_errors = [e for e in errors if e["field"] == "email"]
        name_errors = [e for e in errors if e["field"] == "name"]
        assert len(email_errors) == 2
        assert len(name_errors) == 2

    def test_falsy_values_are_not_treated_as_blank(self) -> None:
        df_num = pl.DataFrame({"row_number": [1, 2, 3], "num": [0, 0, 1]})
        num_errors = collect_infile_duplicates(df_num, ["num"])
        assert len(num_errors) == 2
        assert {e["row_number"] for e in num_errors} == {1, 2}

        df_bool = pl.DataFrame({"row_number": [1, 2, 3], "enabled": [False, False, True]})
        bool_errors = collect_infile_duplicates(df_bool, ["enabled"])
        assert len(bool_errors) == 2
        assert {e["row_number"] for e in bool_errors} == {1, 2}


class TestBuildConflictErrors:
    def test_has_conflicts(self) -> None:
        df = pl.DataFrame(
            {
                "row_number": [1, 2, 3],
                "email": ["a@b.com", "c@d.com", "a@b.com"],
            }
        )
        errors = build_conflict_errors(df, "email", ["a@b.com"], reason="already exists")
        assert len(errors) == 2
        assert all(e["type"] == "db_conflict" for e in errors)

    def test_empty_conflict_values(self) -> None:
        df = pl.DataFrame({"row_number": [1], "email": ["a@b.com"]})
        errors = build_conflict_errors(df, "email", [], reason="exists")
        assert len(errors) == 0

    def test_field_not_present(self) -> None:
        df = pl.DataFrame({"row_number": [1], "name": ["alice"]})
        errors = build_conflict_errors(df, "nonexistent", ["val"], reason="reason")
        assert len(errors) == 0

    def test_empty_dataframe(self) -> None:
        df = pl.DataFrame({"row_number": [], "email": []}).cast({"row_number": pl.Int64, "email": pl.Utf8})
        errors = build_conflict_errors(df, "email", ["a@b.com"], reason="exists")
        assert len(errors) == 0

    def test_falsy_conflict_values_are_detected(self) -> None:
        df = pl.DataFrame({"row_number": [1, 2, 3], "code": [0, 1, 0]})
        errors = build_conflict_errors(df, "code", [0], reason="already exists")
        assert len(errors) == 2
        assert {e["row_number"] for e in errors} == {1, 3}
