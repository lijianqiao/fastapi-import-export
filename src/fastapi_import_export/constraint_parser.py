"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: constraint_parser.py
@DateTime: 2026-02-08
@Docs: Multi-database unique constraint error parsing.
多数据库唯一约束错误解析。

Provides parsers for PostgreSQL, MySQL/MariaDB, SQLite, SQL Server, and Oracle
unique constraint error messages. Each parser extracts structured information
(columns, values, constraint name) from raw error text.

提供 PostgreSQL、MySQL/MariaDB、SQLite、SQL Server、Oracle 的唯一约束错误
解析器。每个解析器从原始错误文本中提取结构化信息（列名、值、约束名）。
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.typing import TableData


@dataclass(frozen=True, slots=True)
class ConstraintDetail:
    """Parsed unique constraint violation detail.

    解析后的唯一约束冲突详情。

    Attributes:
        columns: Column names involved in the constraint.
            约束涉及的列名列表。
        values: Conflicting values corresponding to columns.
            与列名对应的冲突值列表。
        constraint_name: Name of the violated constraint (if available).
            违反的约束名称（如果可用）。
        db_type: Database type identifier.
            数据库类型标识符。
    """

    columns: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    constraint_name: str | None = None
    db_type: str = "unknown"


# ---------------------------------------------------------------------------
# Database-specific parsers / 数据库特定解析器
# ---------------------------------------------------------------------------

_ConstraintParser = Callable[[str, str], ConstraintDetail | None]


def _parse_pg(text: str, detail_text: str) -> ConstraintDetail | None:
    """Parse PostgreSQL unique constraint error.

    解析 PostgreSQL 唯一约束错误。

    Matches format: ``Key (col1, col2)=(val1, val2) already exists.``
    匹配格式：``Key (col1, col2)=(val1, val2) already exists.``

    Args:
        text: Primary error message text.
            主错误信息文本。
        detail_text: Detail text (e.g. from PG orig.detail).
            详细错误文本（如 PG orig.detail）。

    Returns:
        ConstraintDetail if matched, None otherwise.
        匹配则返回 ConstraintDetail，否则返回 None。
    """
    # Try detail_text first, then main text / 先尝试 detail_text，再尝试主文本
    for source in (detail_text, text):
        if not source:
            continue
        m = re.search(r"Key\s+\((?P<cols>[^)]+)\)=\((?P<vals>[^)]+)\)\s+already exists\.", source)
        if m:
            cols = [c.strip() for c in str(m.group("cols")).split(",") if c.strip()]
            vals = [v.strip() for v in str(m.group("vals")).split(",") if v.strip()]
            # Extract constraint name from main text / 从主文本提取约束名
            cname = None
            cm = re.search(r'unique constraint "(?P<name>[^"]+)"', text)
            if cm:
                cname = cm.group("name")
            return ConstraintDetail(columns=cols, values=vals, constraint_name=cname, db_type="postgresql")
    return None


def _parse_mysql(text: str, detail_text: str) -> ConstraintDetail | None:
    """Parse MySQL/MariaDB unique constraint error.

    解析 MySQL/MariaDB 唯一约束错误。

    Matches format: ``Duplicate entry 'val' for key 'key_name'``
    匹配格式：``Duplicate entry 'val' for key 'key_name'``

    Args:
        text: Primary error message text.
            主错误信息文本。
        detail_text: Detail text (usually empty for MySQL).
            详细错误文本（MySQL 通常为空）。

    Returns:
        ConstraintDetail if matched, None otherwise.
        匹配则返回 ConstraintDetail，否则返回 None。
    """
    combined = f"{text} {detail_text}"
    m = re.search(r"Duplicate entry '(?P<val>[^']+)' for key '(?P<key>[^']+)'", combined, re.IGNORECASE)
    if not m:
        return None
    val = m.group("val")
    key_name = m.group("key")
    # MySQL composite key values are joined by '-' / MySQL 组合键值用 '-' 连接
    values = [v.strip() for v in val.split("-") if v.strip()] if "-" in val else [val]
    return ConstraintDetail(columns=[], values=values, constraint_name=key_name, db_type="mysql")


def _parse_sqlite(text: str, detail_text: str) -> ConstraintDetail | None:
    """Parse SQLite unique constraint error.

    解析 SQLite 唯一约束错误。

    Matches format: ``UNIQUE constraint failed: table.col1, table.col2``
    匹配格式：``UNIQUE constraint failed: table.col1, table.col2``

    Args:
        text: Primary error message text.
            主错误信息文本。
        detail_text: Detail text (usually empty for SQLite).
            详细错误文本（SQLite 通常为空）。

    Returns:
        ConstraintDetail if matched, None otherwise.
        匹配则返回 ConstraintDetail，否则返回 None。
    """
    combined = f"{text} {detail_text}"
    m = re.search(r"UNIQUE constraint failed:\s*(?P<cols>.+?)(?:\s*$|\s*\n)", combined, re.IGNORECASE)
    if not m:
        return None
    raw_cols = m.group("cols")
    # Strip table prefix (e.g. "devices.name" -> "name") / 去除表名前缀
    columns = []
    for part in raw_cols.split(","):
        part = part.strip()
        if "." in part:
            columns.append(part.split(".")[-1].strip())
        elif part:
            columns.append(part)
    return ConstraintDetail(columns=columns, values=[], constraint_name=None, db_type="sqlite")


def _parse_mssql(text: str, detail_text: str) -> ConstraintDetail | None:
    """Parse SQL Server unique constraint error.

    解析 SQL Server 唯一约束错误。

    Matches format:
        ``Violation of UNIQUE KEY constraint 'constraint_name'.
        Cannot insert duplicate key in object 'dbo.table'.
        The duplicate key value is (val1, val2).``
    匹配格式：
        ``Violation of UNIQUE KEY constraint 'constraint_name'.
        Cannot insert duplicate key in object 'dbo.table'.
        The duplicate key value is (val1, val2).``

    Args:
        text: Primary error message text.
            主错误信息文本。
        detail_text: Detail text.
            详细错误文本。

    Returns:
        ConstraintDetail if matched, None otherwise.
        匹配则返回 ConstraintDetail，否则返回 None。
    """
    combined = f"{text} {detail_text}"
    cm = re.search(r"Violation of UNIQUE KEY constraint '(?P<name>[^']+)'", combined, re.IGNORECASE)
    constraint_name = cm.group("name") if cm else None

    vm = re.search(r"The duplicate key value is \((?P<vals>[^)]+)\)", combined, re.IGNORECASE)
    values: list[str] = []
    if vm:
        values = [v.strip() for v in vm.group("vals").split(",") if v.strip()]

    if constraint_name or values:
        return ConstraintDetail(columns=[], values=values, constraint_name=constraint_name, db_type="mssql")
    return None


def _parse_oracle(text: str, detail_text: str) -> ConstraintDetail | None:
    """Parse Oracle unique constraint error.

    解析 Oracle 唯一约束错误。

    Matches format: ``ORA-00001: unique constraint (SCHEMA.NAME) violated``
    匹配格式：``ORA-00001: unique constraint (SCHEMA.NAME) violated``

    Args:
        text: Primary error message text.
            主错误信息文本。
        detail_text: Detail text.
            详细错误文本。

    Returns:
        ConstraintDetail if matched, None otherwise.
        匹配则返回 ConstraintDetail，否则返回 None。
    """
    combined = f"{text} {detail_text}"
    m = re.search(r"ORA-00001:\s*unique constraint \((?P<name>[^)]+)\) violated", combined, re.IGNORECASE)
    if not m:
        return None
    constraint_name = m.group("name")
    return ConstraintDetail(columns=[], values=[], constraint_name=constraint_name, db_type="oracle")


# Parser registry (order: most specific first) / 解析器注册表（优先级：最具体的排前面）
_PARSERS: tuple[_ConstraintParser, ...] = (
    _parse_pg,
    _parse_mysql,
    _parse_sqlite,
    _parse_mssql,
    _parse_oracle,
)


# ---------------------------------------------------------------------------
# Public API / 公开 API
# ---------------------------------------------------------------------------


def parse_unique_constraint_error(text: str, *, detail_text: str = "") -> ConstraintDetail | None:
    """Try all registered parsers in order until one matches.

    按顺序尝试所有已注册的解析器，直到匹配为止。

    Args:
        text: Primary error message text.
            主错误信息文本。
        detail_text: Optional detail text (e.g. from PG orig.detail).
            可选的详细错误文本（如 PG orig.detail）。

    Returns:
        ConstraintDetail if any parser matched, None otherwise.
        若有解析器匹配则返回 ConstraintDetail，否则返回 None。
    """
    for parser in _PARSERS:
        result = parser(text, detail_text)
        if result is not None:
            return result
    return None


# Unique constraint keywords for all supported databases.
# 所有支持的数据库唯一约束关键字。
_UNIQUE_KEYWORDS = (
    "duplicate key value violates unique constraint",  # PostgreSQL
    "duplicate entry",                                  # MySQL / MariaDB
    "unique constraint failed",                         # SQLite
    "violation of unique key constraint",               # SQL Server
    "ora-00001",                                        # Oracle
    "already exists",                                   # generic
)


def is_unique_constraint_error(text: str, *, detail_text: str = "") -> bool:
    """Check if an error message indicates a unique constraint violation.

    检查错误信息是否表示唯一约束冲突。

    Supports PostgreSQL, MySQL/MariaDB, SQLite, SQL Server, and Oracle.
    支持 PostgreSQL、MySQL/MariaDB、SQLite、SQL Server、Oracle。

    Args:
        text: Primary error message text.
            主错误信息文本。
        detail_text: Optional detail text.
            可选的详细错误文本。

    Returns:
        True if a unique constraint keyword is found.
        若找到唯一约束关键字则返回 True。
    """
    combined = f"{text} {detail_text}".lower()
    return any(kw in combined for kw in _UNIQUE_KEYWORDS)


def find_conflict_row_numbers(
    df: TableData,
    *,
    columns: list[str],
    values: list[str],
    limit: int = 50,
) -> list[int]:
    """Find row numbers of rows with given column values.

    查找给定列值的行号。

    Args:
        df: The DataFrame to search.
            要搜索的 DataFrame。
        columns: List of column names to match.
            要匹配的列名列表。
        values: List of values to match.
            要匹配的值列表。
        limit: Maximum number of row numbers to return.
            返回的最大行号数量。

    Returns:
        A list of row numbers where the specified columns have the given values.
            指定列值匹配的行号列表。
    """
    try:
        import polars as pl
    except Exception:  # pragma: no cover / 覆盖忽略
        return []

    if df.is_empty():
        return []
    # Ensure row_number column exists / 确保 row_number 列存在
    if "row_number" not in df.columns:
        return []
    for c in columns:
        if c not in df.columns:
            return []

    exprs: list[Any] = []
    for c, v in zip(columns, values, strict=False):
        exprs.append(pl.col(c).cast(pl.Utf8, strict=False) == v)
    if not exprs:
        return []
    filt = exprs[0]
    for e in exprs[1:]:
        filt = filt & e
    matched = df.filter(filt).select("row_number")
    if matched.is_empty():
        return []
    return [int(x) for x in matched.get_column("row_number").to_list()[:limit]]


def raise_unique_conflict(
    exc: Exception,
    valid_df: TableData,
    *,
    detail_text: str = "",
    extra_details: dict[str, Any] | None = None,
) -> None:
    """Parse a unique-constraint error and raise a user-friendly ImportExportError.

    解析唯一约束错误并抛出用户友好的 ImportExportError。

    Supports PostgreSQL, MySQL/MariaDB, SQLite, SQL Server, and Oracle.
    支持 PostgreSQL、MySQL/MariaDB、SQLite、SQL Server、Oracle。

    If the error text contains parseable column/value info, this function raises
    ``ImportExportError`` with conflict details and affected row numbers.
    Otherwise it raises a generic unique-conflict ``ImportExportError``.

    若错误文本包含可解析的列/值信息，则抛出带有冲突详情和受影响行号的
    ``ImportExportError``；否则抛出通用唯一冲突 ``ImportExportError``。

    Args:
        exc: The original exception.
            原始异常。
        valid_df: DataFrame of valid rows (used to locate conflict row numbers).
            有效行 DataFrame（用于定位冲突行号）。
        detail_text: Optional detail text to parse (e.g. from PG orig.detail).
            可选的详细错误文本（如 PG orig.detail）。
        extra_details: Optional extra details to merge into the error payload.
            可选的额外详情字典，会合并到错误载荷中。

    Raises:
        ImportExportError: Always raised with appropriate conflict information.
            始终抛出，并附带相应的冲突信息。
    """
    text = str(exc)
    parsed = parse_unique_constraint_error(text, detail_text=detail_text)

    if parsed and (parsed.columns or parsed.values or parsed.constraint_name):
        row_numbers: list[int] = []
        if parsed.columns and parsed.values:
            row_numbers = find_conflict_row_numbers(
                valid_df, columns=parsed.columns, values=parsed.values
            )
        payload: dict[str, Any] = {
            "columns": parsed.columns,
            "values": parsed.values,
            "row_numbers": row_numbers,
            "db_type": parsed.db_type,
        }
        if parsed.constraint_name:
            payload["constraint_name"] = parsed.constraint_name
        if extra_details:
            payload.update(extra_details)

        # Build human-readable conflict summary / 构建可读的冲突摘要
        if parsed.columns and parsed.values:
            conflict = ", ".join(
                f"{c}={v}" for c, v in zip(parsed.columns, parsed.values, strict=False)
            )
        elif parsed.values:
            conflict = ", ".join(parsed.values)
        elif parsed.columns:
            conflict = ", ".join(parsed.columns)
        else:
            conflict = parsed.constraint_name or "unknown"

        raise ImportExportError(
            message=(
                f"Unique constraint conflict: {conflict} already exists (may include soft-deleted records)."
                f" / 唯一约束冲突：{conflict} 已存在（可能包含软删除记录）。"
            ),
            details=payload,
        ) from exc

    raise ImportExportError(
        message=(
            "Unique constraint conflict: import data duplicates existing keys (may include soft-deleted records)."
            " / 唯一约束冲突：导入数据与现有数据存在重复键（可能包含软删除记录）。"
        ),
        details=extra_details or {"error": text},
    ) from exc
