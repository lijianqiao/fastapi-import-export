"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: db_validation.py
@DateTime: 2026-02-08
@Docs: DB validation facade with optional backend.
数据库校验门面（可选后端）。
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi_import_export.exceptions import ImportExportError

type KeyTuple = tuple[str, ...]


class DbCheckFn(Protocol):
    """Protocol for asynchronous database check functions.
    异步数据库校验函数协议。

    The callable should accept (db, keys, *, allow_overwrite=False) and return
    a mapping from KeyTuple to conflict details.
    调用签名为 (db, keys, *, allow_overwrite=False)，返回 KeyTuple 到冲突详情的映射。
    """

    async def __call__(
        self,
        db: Any,
        keys: list[KeyTuple],
        *,
        allow_overwrite: bool = False,
    ) -> dict[KeyTuple, dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class DbCheckSpec:
    """
    Db check specification.
    数据库校验规范。

    Attributes:
        key_fields: Key fields list.
        key_fields: key 字段列表。
        check_fn: DB check function.
        check_fn: 数据库校验函数。
        field: Error field name.
        field: 错误字段名。
        message: Default error message.
        message: 默认错误消息。
        type: Error type.
        type: 错误类型。
    """

    key_fields: list[str]
    check_fn: DbCheckFn
    field: str | None = None
    message: str = "DB check failed / 数据库校验失败"
    type: str = "db_check"


def _load_backend() -> Any:
    """Load optional backend module for DB validation (polars).
    加载数据库校验可选后端模块（polars）。

    Returns:
        The backend module providing DB validation helpers.
            提供数据库校验辅助的后端模块。

    Raises:
        ImportExportError: When optional dependencies are missing.
            当缺少可选依赖时抛出 ImportExportError。
    """
    try:
        from fastapi_import_export import db_validation_polars

        return db_validation_polars
    except Exception as exc:  # pragma: no cover / 覆盖忽略
        raise ImportExportError(
            message="Missing optional dependencies for db validation. Install extras: polars / 缺少数据库校验可选依赖，请安装: polars",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


def build_key_to_row_numbers(df: Any, key_fields: Iterable[str]) -> dict[KeyTuple, list[int]]:
    """
    Build mapping: key -> row_number list.
    构建映射：key -> 行号列表。

    Args:
        df: Input DataFrame.
        df: 输入数据框。
        key_fields: Key fields list.
        key_fields: key 字段列表。
    Returns:
        Mapping from key tuple to list of row numbers (1-based).
        key 元组到行号列表（基于 1）的映射。
    """
    backend = _load_backend()
    return backend.build_key_to_row_numbers(df, key_fields)


def build_db_conflict_errors(
    *,
    key_to_row_numbers: dict[KeyTuple, list[int]],
    conflicts: dict[KeyTuple, dict[str, Any]],
    field: str | None,
    default_message: str,
    type: str,
    max_rows_per_key: int = 50,
) -> list[dict[str, Any]]:
    """
    Convert db conflict map to error list.
    将数据库冲突映射转换为错误列表。

    Args:
        key_to_row_numbers: Mapping from key tuple to list of row numbers (1-based).
            key 元组到行号列表（基于 1）的映射。
        conflicts: Mapping from key tuple to conflict details.
            key 元组到冲突详情的映射。
        field: Error field name.
            错误字段名。
        default_message: Default error message.
            默认错误消息。
        type: Error type.
            错误类型。
        max_rows_per_key: Maximum number of rows to include per key in error list.
            每个 key 在错误列表中包含的最大行数。
    """
    backend = _load_backend()
    return backend.build_db_conflict_errors(
        key_to_row_numbers=key_to_row_numbers,
        conflicts=conflicts,
        field=field,
        default_message=default_message,
        type=type,
        max_rows_per_key=max_rows_per_key,
    )


async def run_db_checks(
    *,
    db: Any,
    df: Any,
    specs: list[DbCheckSpec],
    allow_overwrite: bool = False,
) -> list[dict[str, Any]]:
    """
    Run database checks and return error list.
    执行数据库校验并返回错误列表。

    Args:
        db: Database connection or context.
            数据库连接或上下文。
        df: Input DataFrame.
            输入数据框。
        specs: List of DbCheckSpec defining checks to run.
            定义要运行的校验的 DbCheckSpec 列表。
        allow_overwrite: Whether to allow overwriting existing values (affects checks).
            是否允许覆盖现有值（影响校验行为）。
    Returns:
        List of error dicts for any detected issues.
            检测到的问题的错误字典列表。
    """
    backend = _load_backend()
    return await backend.run_db_checks(db=db, df=df, specs=specs, allow_overwrite=allow_overwrite)
