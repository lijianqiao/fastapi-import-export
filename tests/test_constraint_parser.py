"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_constraint_parser.py
@DateTime: 2026-02-08
@Docs: Tests for multi-database unique constraint error parsing.
多数据库唯一约束错误解析测试。
"""

import polars as pl
import pytest

from fastapi_import_export.constraint_parser import (
    ConstraintDetail,
    find_conflict_row_numbers,
    is_unique_constraint_error,
    parse_unique_constraint_error,
    raise_unique_conflict,
)
from fastapi_import_export.exceptions import ImportExportError


# ---------------------------------------------------------------------------
# PostgreSQL / PostgreSQL 测试
# ---------------------------------------------------------------------------


class TestParsePostgreSQL:
    """PostgreSQL unique constraint error parsing tests.

    PostgreSQL 唯一约束错误解析测试。
    """

    def test_pg_key_detail(self) -> None:
        """Parse PG error with Key detail / 解析带 Key detail 的 PG 错误。"""
        text = 'duplicate key value violates unique constraint "uq_devices_name"'
        detail = "Key (name)=(Widget A) already exists."
        result = parse_unique_constraint_error(text, detail_text=detail)
        assert result is not None
        assert result.db_type == "postgresql"
        assert result.columns == ["name"]
        assert result.values == ["Widget A"]
        assert result.constraint_name == "uq_devices_name"

    def test_pg_composite_key(self) -> None:
        """Parse PG composite key / 解析 PG 组合键。"""
        text = 'duplicate key value violates unique constraint "uq_devices_name_serial"'
        detail = "Key (name, serial_no)=(Widget A, SN001) already exists."
        result = parse_unique_constraint_error(text, detail_text=detail)
        assert result is not None
        assert result.db_type == "postgresql"
        assert result.columns == ["name", "serial_no"]
        assert result.values == ["Widget A", "SN001"]
        assert result.constraint_name == "uq_devices_name_serial"

    def test_pg_key_in_main_text(self) -> None:
        """Key info in main text without detail / 主文本中包含 Key 信息（无 detail）。"""
        text = "Key (email)=(test@example.com) already exists."
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "postgresql"
        assert result.columns == ["email"]
        assert result.values == ["test@example.com"]
        assert result.constraint_name is None

    def test_pg_no_match(self) -> None:
        """Non-PG text returns None / 非 PG 文本返回 None。"""
        result = parse_unique_constraint_error("some other error")
        assert result is None


# ---------------------------------------------------------------------------
# MySQL / MariaDB / MySQL 测试
# ---------------------------------------------------------------------------


class TestParseMySQL:
    """MySQL/MariaDB unique constraint error parsing tests.

    MySQL/MariaDB 唯一约束错误解析测试。
    """

    def test_mysql_single_value(self) -> None:
        """Parse MySQL single value duplicate / 解析 MySQL 单值重复。"""
        text = "Duplicate entry 'alice@example.com' for key 'ix_users_email'"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "mysql"
        assert result.values == ["alice@example.com"]
        assert result.constraint_name == "ix_users_email"
        assert result.columns == []

    def test_mysql_composite_value(self) -> None:
        """Parse MySQL composite key value (joined by -) / 解析 MySQL 组合键值。"""
        text = "Duplicate entry 'Widget A-SN001' for key 'uq_name_serial'"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "mysql"
        assert result.values == ["Widget A", "SN001"]
        assert result.constraint_name == "uq_name_serial"

    def test_mysql_primary(self) -> None:
        """Parse MySQL PRIMARY key violation / 解析 MySQL PRIMARY 键冲突。"""
        text = "Duplicate entry '42' for key 'PRIMARY'"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "mysql"
        assert result.values == ["42"]
        assert result.constraint_name == "PRIMARY"

    def test_mysql_case_insensitive(self) -> None:
        """MySQL error matching is case-insensitive / MySQL 错误匹配不区分大小写。"""
        text = "duplicate ENTRY 'foo' FOR KEY 'bar'"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "mysql"


# ---------------------------------------------------------------------------
# SQLite / SQLite 测试
# ---------------------------------------------------------------------------


class TestParseSQLite:
    """SQLite unique constraint error parsing tests.

    SQLite 唯一约束错误解析测试。
    """

    def test_sqlite_single_column(self) -> None:
        """Parse SQLite single column constraint / 解析 SQLite 单列约束。"""
        text = "UNIQUE constraint failed: devices.name"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "sqlite"
        assert result.columns == ["name"]
        assert result.constraint_name is None
        assert result.values == []

    def test_sqlite_composite_columns(self) -> None:
        """Parse SQLite composite column constraint / 解析 SQLite 多列约束。"""
        text = "UNIQUE constraint failed: devices.name, devices.serial_no"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "sqlite"
        assert result.columns == ["name", "serial_no"]

    def test_sqlite_no_table_prefix(self) -> None:
        """Parse SQLite constraint without table prefix / 解析无表名前缀的 SQLite 约束。"""
        text = "UNIQUE constraint failed: email"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "sqlite"
        assert result.columns == ["email"]

    def test_sqlite_case_insensitive(self) -> None:
        """SQLite error matching is case-insensitive / SQLite 错误匹配不区分大小写。"""
        text = "unique CONSTRAINT FAILED: users.email"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "sqlite"
        assert result.columns == ["email"]

    def test_sqlite_in_detail_text(self) -> None:
        """SQLite error in detail_text / detail_text 中的 SQLite 错误。"""
        result = parse_unique_constraint_error(
            "IntegrityError", detail_text="UNIQUE constraint failed: devices.name"
        )
        assert result is not None
        assert result.db_type == "sqlite"
        assert result.columns == ["name"]


# ---------------------------------------------------------------------------
# SQL Server / SQL Server 测试
# ---------------------------------------------------------------------------


class TestParseMSSQL:
    """SQL Server unique constraint error parsing tests.

    SQL Server 唯一约束错误解析测试。
    """

    def test_mssql_full_message(self) -> None:
        """Parse SQL Server full unique key violation / 解析完整的 SQL Server 唯一键冲突。"""
        text = (
            "Violation of UNIQUE KEY constraint 'UQ_Devices_Name'. "
            "Cannot insert duplicate key in object 'dbo.Devices'. "
            "The duplicate key value is (Widget A)."
        )
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "mssql"
        assert result.constraint_name == "UQ_Devices_Name"
        assert result.values == ["Widget A"]

    def test_mssql_composite_values(self) -> None:
        """Parse SQL Server composite key values / 解析 SQL Server 组合键值。"""
        text = (
            "Violation of UNIQUE KEY constraint 'UQ_Dev_NS'. "
            "The duplicate key value is (Widget A, SN001)."
        )
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "mssql"
        assert result.values == ["Widget A", "SN001"]
        assert result.constraint_name == "UQ_Dev_NS"

    def test_mssql_constraint_only(self) -> None:
        """Parse SQL Server with only constraint name / 仅有约束名的 SQL Server 错误。"""
        text = "Violation of UNIQUE KEY constraint 'UQ_Name'."
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "mssql"
        assert result.constraint_name == "UQ_Name"
        assert result.values == []


# ---------------------------------------------------------------------------
# Oracle / Oracle 测试
# ---------------------------------------------------------------------------


class TestParseOracle:
    """Oracle unique constraint error parsing tests.

    Oracle 唯一约束错误解析测试。
    """

    def test_oracle_basic(self) -> None:
        """Parse Oracle ORA-00001 / 解析 Oracle ORA-00001。"""
        text = "ORA-00001: unique constraint (MYSCHEMA.UQ_DEVICES_NAME) violated"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "oracle"
        assert result.constraint_name == "MYSCHEMA.UQ_DEVICES_NAME"
        assert result.columns == []
        assert result.values == []

    def test_oracle_lowercase(self) -> None:
        """Oracle matching is case-insensitive / Oracle 匹配不区分大小写。"""
        text = "ora-00001: unique constraint (hr.pk_emp) violated"
        result = parse_unique_constraint_error(text)
        assert result is not None
        assert result.db_type == "oracle"
        assert result.constraint_name == "hr.pk_emp"

    def test_oracle_in_detail_text(self) -> None:
        """Oracle error in detail_text / detail_text 中的 Oracle 错误。"""
        result = parse_unique_constraint_error(
            "DatabaseError",
            detail_text="ORA-00001: unique constraint (SYS.UQ_ID) violated",
        )
        assert result is not None
        assert result.db_type == "oracle"
        assert result.constraint_name == "SYS.UQ_ID"


# ---------------------------------------------------------------------------
# is_unique_constraint_error / 唯一约束错误检测
# ---------------------------------------------------------------------------


class TestIsUniqueConstraintError:
    """Tests for is_unique_constraint_error function.

    is_unique_constraint_error 函数测试。
    """

    @pytest.mark.parametrize(
        "text",
        [
            'duplicate key value violates unique constraint "uq_name"',
            "Duplicate entry 'foo' for key 'bar'",
            "UNIQUE constraint failed: devices.name",
            "Violation of UNIQUE KEY constraint 'UQ_Name'",
            "ORA-00001: unique constraint (SCHEMA.NAME) violated",
            "Key (id)=(1) already exists.",
        ],
        ids=["postgresql", "mysql", "sqlite", "mssql", "oracle", "generic_already_exists"],
    )
    def test_positive_cases(self, text: str) -> None:
        """Known unique constraint patterns should return True / 已知唯一约束模式应返回 True。"""
        assert is_unique_constraint_error(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "NOT NULL constraint failed: devices.name",
            "CHECK constraint failed",
            "foreign key constraint fails",
            "division by zero",
            "connection refused",
            "",
        ],
        ids=["not_null", "check", "foreign_key", "generic", "connection", "empty"],
    )
    def test_negative_cases(self, text: str) -> None:
        """Non-unique errors should return False / 非唯一约束错误应返回 False。"""
        assert is_unique_constraint_error(text) is False

    def test_detail_text_only(self) -> None:
        """Keyword in detail_text only / 仅 detail_text 中包含关键字。"""
        assert is_unique_constraint_error("Error", detail_text="duplicate entry 'x' for key 'y'") is True

    def test_case_insensitive(self) -> None:
        """Detection is case-insensitive / 检测不区分大小写。"""
        assert is_unique_constraint_error("DUPLICATE KEY VALUE VIOLATES UNIQUE CONSTRAINT") is True


# ---------------------------------------------------------------------------
# find_conflict_row_numbers / 冲突行号查找
# ---------------------------------------------------------------------------


class TestFindConflictRowNumbers:
    """Tests for find_conflict_row_numbers function.

    find_conflict_row_numbers 函数测试。
    """

    def test_single_match(self, sample_polars_df: pl.DataFrame) -> None:
        """Find a single matching row / 查找单个匹配行。"""
        rows = find_conflict_row_numbers(
            sample_polars_df, columns=["username"], values=["bob"]
        )
        assert rows == [2]

    def test_no_match(self, sample_polars_df: pl.DataFrame) -> None:
        """No matching rows returns empty list / 无匹配行返回空列表。"""
        rows = find_conflict_row_numbers(
            sample_polars_df, columns=["username"], values=["nonexistent"]
        )
        assert rows == []

    def test_empty_df(self) -> None:
        """Empty DataFrame returns empty list / 空 DataFrame 返回空列表。"""
        df = pl.DataFrame({"row_number": [], "name": []})
        rows = find_conflict_row_numbers(df, columns=["name"], values=["x"])
        assert rows == []

    def test_missing_row_number_column(self) -> None:
        """DataFrame without row_number returns empty list / 无 row_number 列返回空列表。"""
        df = pl.DataFrame({"name": ["a", "b"]})
        rows = find_conflict_row_numbers(df, columns=["name"], values=["a"])
        assert rows == []

    def test_missing_search_column(self, sample_polars_df: pl.DataFrame) -> None:
        """Missing search column returns empty list / 搜索列不存在返回空列表。"""
        rows = find_conflict_row_numbers(
            sample_polars_df, columns=["nonexistent_col"], values=["alice"]
        )
        assert rows == []

    def test_multi_column_match(self) -> None:
        """Match on multiple columns / 多列匹配。"""
        df = pl.DataFrame(
            {
                "row_number": [1, 2, 3],
                "name": ["Alice", "Alice", "Bob"],
                "code": ["A1", "A2", "A1"],
            }
        )
        rows = find_conflict_row_numbers(df, columns=["name", "code"], values=["Alice", "A1"])
        assert rows == [1]

    def test_limit(self) -> None:
        """Limit restricts returned rows / limit 限制返回行数。"""
        df = pl.DataFrame(
            {
                "row_number": list(range(1, 101)),
                "name": ["same"] * 100,
            }
        )
        rows = find_conflict_row_numbers(df, columns=["name"], values=["same"], limit=5)
        assert len(rows) == 5

    def test_empty_columns_and_values(self, sample_polars_df: pl.DataFrame) -> None:
        """Empty columns/values returns empty list / 空列名和值返回空列表。"""
        rows = find_conflict_row_numbers(sample_polars_df, columns=[], values=[])
        assert rows == []


# ---------------------------------------------------------------------------
# raise_unique_conflict / 抛出唯一约束冲突
# ---------------------------------------------------------------------------


class TestRaiseUniqueConflict:
    """Tests for raise_unique_conflict function.

    raise_unique_conflict 函数测试。
    """

    def test_pg_error_raises_with_details(self, sample_polars_df: pl.DataFrame) -> None:
        """PG error raises ImportExportError with parsed details / PG 错误抛出含解析详情的 ImportExportError。"""
        exc = Exception(
            'duplicate key value violates unique constraint "uq_users_username" '
        )
        detail = "Key (username)=(bob) already exists."
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(exc, sample_polars_df, detail_text=detail)
        err = exc_info.value
        assert "bob" in err.message
        assert err.details is not None
        assert err.details["db_type"] == "postgresql"
        assert err.details["columns"] == ["username"]
        assert err.details["values"] == ["bob"]
        assert 2 in err.details["row_numbers"]

    def test_mysql_error_raises(self, sample_polars_df: pl.DataFrame) -> None:
        """MySQL error raises ImportExportError / MySQL 错误抛出 ImportExportError。"""
        exc = Exception("Duplicate entry 'alice@example.com' for key 'ix_users_email'")
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(exc, sample_polars_df)
        err = exc_info.value
        assert "alice@example.com" in err.message
        assert err.details is not None
        assert err.details["db_type"] == "mysql"

    def test_sqlite_error_raises(self, sample_polars_df: pl.DataFrame) -> None:
        """SQLite error raises ImportExportError with column info / SQLite 错误抛出含列信息的 ImportExportError。"""
        exc = Exception("UNIQUE constraint failed: users.email")
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(exc, sample_polars_df)
        err = exc_info.value
        assert "email" in err.message
        assert err.details is not None
        assert err.details["db_type"] == "sqlite"
        assert err.details["columns"] == ["email"]

    def test_mssql_error_raises(self, sample_polars_df: pl.DataFrame) -> None:
        """SQL Server error raises ImportExportError / SQL Server 错误抛出 ImportExportError。"""
        exc = Exception(
            "Violation of UNIQUE KEY constraint 'UQ_Name'. "
            "The duplicate key value is (bob)."
        )
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(exc, sample_polars_df)
        err = exc_info.value
        assert "bob" in err.message
        assert err.details is not None
        assert err.details["db_type"] == "mssql"

    def test_oracle_error_raises(self, sample_polars_df: pl.DataFrame) -> None:
        """Oracle error raises ImportExportError / Oracle 错误抛出 ImportExportError。"""
        exc = Exception("ORA-00001: unique constraint (MYSCHEMA.UQ_DEVICES_NAME) violated")
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(exc, sample_polars_df)
        err = exc_info.value
        assert "MYSCHEMA.UQ_DEVICES_NAME" in err.message
        assert err.details is not None
        assert err.details["db_type"] == "oracle"

    def test_generic_unique_error_fallback(self, sample_polars_df: pl.DataFrame) -> None:
        """Unknown format falls back to generic message / 未知格式回退到通用消息。"""
        exc = Exception("some integrity error with unique constraint violation unknown format")
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(exc, sample_polars_df)
        err = exc_info.value
        assert "unique" in err.message.lower()
        assert err.details is not None

    def test_extra_details_merged(self, sample_polars_df: pl.DataFrame) -> None:
        """Extra details are merged into error payload / 额外详情被合并到错误载荷中。"""
        exc = Exception(
            'duplicate key value violates unique constraint "uq_users_username"'
        )
        detail = "Key (username)=(alice) already exists."
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(
                exc,
                sample_polars_df,
                detail_text=detail,
                extra_details={"constraint": "uq_users_username"},
            )
        err = exc_info.value
        assert err.details is not None
        assert err.details["constraint"] == "uq_users_username"

    def test_empty_df_no_row_numbers(self) -> None:
        """Empty DataFrame yields empty row_numbers / 空 DataFrame 产生空 row_numbers。"""
        df = pl.DataFrame({"row_number": [], "username": []})
        exc = Exception(
            'duplicate key value violates unique constraint "uq_test"'
        )
        detail = "Key (username)=(alice) already exists."
        with pytest.raises(ImportExportError) as exc_info:
            raise_unique_conflict(exc, df, detail_text=detail)
        err = exc_info.value
        assert err.details is not None
        assert err.details["row_numbers"] == []


# ---------------------------------------------------------------------------
# parse_unique_constraint_error priority / 解析优先级
# ---------------------------------------------------------------------------


class TestParserPriority:
    """Tests for parser priority and edge cases.

    解析器优先级和边界情况测试。
    """

    def test_no_match_returns_none(self) -> None:
        """Completely unrelated text returns None / 完全无关文本返回 None。"""
        assert parse_unique_constraint_error("connection timeout") is None

    def test_empty_text_returns_none(self) -> None:
        """Empty text returns None / 空文本返回 None。"""
        assert parse_unique_constraint_error("") is None

    def test_pg_takes_priority_over_generic(self) -> None:
        """PG parser takes priority over generic fallback / PG 解析器优先于通用 fallback。"""
        text = 'duplicate key value violates unique constraint "uq_test"'
        detail = "Key (name)=(Widget A) already exists."
        result = parse_unique_constraint_error(text, detail_text=detail)
        assert result is not None
        assert result.db_type == "postgresql"
