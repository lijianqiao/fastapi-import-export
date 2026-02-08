"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_validation_polars.py
@DateTime: 2026-02-08
@Docs: Tests for validation_polars.py module.
validation_polars.py 模块测试。
"""

import polars as pl

from fastapi_import_export.validation_polars import (
    build_conflict_errors,
    collect_infile_duplicates,
)


class TestCollectInfileDuplicates:
    """Tests for collect_infile_duplicates.
    collect_infile_duplicates 测试。
    """

    def test_has_duplicates(self) -> None:
        """Detect duplicate values / 检测重复值。"""
        df = pl.DataFrame(
            {
                "row_number": [1, 2, 3],
                "email": ["a@b.com", "a@b.com", "c@d.com"],
            }
        )
        errors = collect_infile_duplicates(df, ["email"])
        assert len(errors) == 2
        assert all(e["type"] == "infile_duplicate" for e in errors)

    def test_no_duplicates(self) -> None:
        """No duplicates returns empty / 无重复返回空列表。"""
        df = pl.DataFrame(
            {
                "row_number": [1, 2],
                "email": ["a@b.com", "c@d.com"],
            }
        )
        errors = collect_infile_duplicates(df, ["email"])
        assert len(errors) == 0

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame returns empty / 空 DataFrame 返回空列表。"""
        df = pl.DataFrame({"row_number": [], "email": []}).cast({"row_number": pl.Int64, "email": pl.Utf8})
        errors = collect_infile_duplicates(df, ["email"])
        assert len(errors) == 0

    def test_field_not_present(self) -> None:
        """Missing field is skipped / 缺失字段被跳过。"""
        df = pl.DataFrame({"row_number": [1], "name": ["alice"]})
        errors = collect_infile_duplicates(df, ["nonexistent"])
        assert len(errors) == 0

    def test_multiple_unique_fields(self) -> None:
        """Multiple fields checked independently / 多字段独立检查。"""
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


class TestBuildConflictErrors:
    """Tests for build_conflict_errors.
    build_conflict_errors 测试。
    """

    def test_has_conflicts(self) -> None:
        """Build errors for conflicting values / 为冲突值构建错误。"""
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
        """Empty conflict set returns empty / 空冲突集返回空列表。"""
        df = pl.DataFrame({"row_number": [1], "email": ["a@b.com"]})
        errors = build_conflict_errors(df, "email", [], reason="exists")
        assert len(errors) == 0

    def test_field_not_present(self) -> None:
        """Missing field returns empty / 缺失字段返回空列表。"""
        df = pl.DataFrame({"row_number": [1], "name": ["alice"]})
        errors = build_conflict_errors(df, "nonexistent", ["val"], reason="reason")
        assert len(errors) == 0

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame returns empty / 空 DataFrame 返回空列表。"""
        df = pl.DataFrame({"row_number": [], "email": []}).cast({"row_number": pl.Int64, "email": pl.Utf8})
        errors = build_conflict_errors(df, "email", ["a@b.com"], reason="exists")
        assert len(errors) == 0
