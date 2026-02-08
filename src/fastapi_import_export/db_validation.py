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
    """
    backend = _load_backend()
    return await backend.run_db_checks(db=db, df=df, specs=specs, allow_overwrite=allow_overwrite)
