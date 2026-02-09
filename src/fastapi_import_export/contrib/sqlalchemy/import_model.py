"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: import_model.py
@DateTime: 2026-02-09
@Docs: SQLAlchemy CSV import adapter.
SQLAlchemy CSV 导入适配器。
"""

import inspect
from typing import Any

from fastapi import UploadFile

from fastapi_import_export.contrib.sqlalchemy.adapters import (
    FieldSpec,
    _require_polars,
    _require_sqlalchemy,
    cast_basic,
    get_field_specs,
    resolve_field_codecs,
    resolve_import_specs,
)
from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.formats import CSV_ALLOWED_EXTENSIONS, CSV_ALLOWED_MIME_TYPES
from fastapi_import_export.importer import ImportResult, ImportStatus
from fastapi_import_export.options import ImportOptions
from fastapi_import_export.schemas import ImportCommitRequest, ImportErrorItem
from fastapi_import_export.service import ImportExportService
from fastapi_import_export.validation_core import ErrorCollector


def _build_column_aliases(specs: list[FieldSpec]) -> dict[str, str]:
    """Build column alias mapping used for file column -> model field resolution.
    构建列别名映射，用于文件列到模型字段的解析。

    Args:
        specs: List of FieldSpec describing importable fields.
            描述可导入字段的 FieldSpec 列表。

    Returns:
        dict[str, str]: Mapping from column name to alias (identity mapping here).
            列名到别名的映射（此处为恒等映射）。
    """
    return {spec.name: spec.name for spec in specs}


def _required_fields(specs: list[FieldSpec]) -> set[str]:
    """Compute the set of required field names for import.
    计算导入时必填字段的集合。

    A field is required when it is not nullable, has no default, and is
    not an auto-incrementing primary key.
    当字段非空、无默认值且不是自增主键时，视为必填字段。

    Args:
        specs: Field specifications to evaluate.
            用于评估的字段规范列表。

    Returns:
        set[str]: Set of required field names.
            必填字段名称集合。
    """
    required: set[str] = set()
    for spec in specs:
        if spec.nullable:
            continue
        if spec.has_default:
            continue
        if spec.primary_key and spec.autoincrement:
            continue
        required.add(spec.name)
    return required


async def _check_db_unique(
    *,
    db: Any,
    model: Any,
    unique_fields: list[str],
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Check the database for existing rows that would conflict with unique fields.
    校验数据库中是否存在与指定唯一字段冲突的记录。

    This function maps incoming rows to key tuples, queries the DB and
    returns an error list plus the rows filtered to exclude conflicting rows.
    该函数将传入行映射为键元组，查询数据库并返回错误列表以及去除冲突行后的行列表。

    Args:
        db: Async DB session/connection.
            异步数据库会话/连接。
        model: SQLAlchemy model class used to query existing values.
            用于查询现有值的 SQLAlchemy 模型类。
        unique_fields: Fields to consider for uniqueness.
            用于唯一性判断的字段列表。
        rows: Candidate rows with a `row_number` for error reporting.
            带有 `row_number` 的候选行，用于错误定位。

    Returns:
        Tuple of (errors, filtered_rows):
            errors: list of error dicts describing conflicts.
                描述冲突的错误字典列表。
            filtered_rows: rows with conflicting entries removed.
                去除冲突条目的行列表。
    """
    sa = _require_sqlalchemy()
    fields = [f for f in unique_fields if f]
    if not fields:
        return [], rows
    columns = []
    for name in fields:
        col = getattr(model, name, None)
        if col is None:
            return [], rows
        columns.append(col)

    key_to_rows: dict[tuple[Any, ...], list[int]] = {}
    for row in rows:
        key = tuple(row.get(f) for f in fields)
        if any(part is None or (isinstance(part, str) and not part.strip()) for part in key):
            continue
        key_to_rows.setdefault(key, []).append(int(row.get("row_number") or 0))

    keys = list(key_to_rows.keys())
    if not keys:
        return [], rows

    if len(columns) == 1:
        values = [k[0] for k in keys]
        stmt = sa.select(columns[0]).where(columns[0].in_(values))
    else:
        stmt = sa.select(*columns).where(sa.tuple_(*columns).in_(keys))
    result = await db.execute(stmt)
    existing: set[tuple[Any, ...]] = set()
    for row in result.all():
        if len(columns) == 1:
            existing.add((row[0],))
        else:
            existing.add(tuple(row))

    if not existing:
        return [], rows

    errors: list[dict[str, Any]] = []
    conflict_rows: set[int] = set()
    for key in existing:
        row_numbers = key_to_rows.get(key, [])
        for rn in row_numbers:
            errors.append(
                {
                    "row_number": int(rn),
                    "field": fields[0] if len(fields) == 1 else None,
                    "message": f"Unique conflict: {fields}={key} / 唯一性冲突: {fields}={key}",
                    "type": "db_unique",
                    "value": key,
                }
            )
            conflict_rows.add(int(rn))

    filtered = [row for row in rows if int(row.get("row_number") or 0) not in conflict_rows]
    return errors, filtered


def _build_validate_fn(
    *,
    model: Any,
    specs: list[FieldSpec],
    unique_fields: list[str] | None,
) -> Any:
    """Build and return an async validate function for imported data.
    构建并返回用于导入数据的异步校验函数。

    The returned function has signature: async def validate_fn(db, df, *, allow_overwrite=False)
    which returns (valid_df, errors).
    返回的函数签名为: async def validate_fn(db, df, *, allow_overwrite=False)，返回 (valid_df, errors)。

    Args:
        model: SQLAlchemy model.
            SQLAlchemy 模型。
        specs: Field specifications to validate/parse.
            用于校验/解析的字段规范。
        unique_fields: Optional per-import unique field list for DB checks.
            可选：用于数据库校验的唯一字段列表。

    Returns:
        Callable: An async validation function.
            异步校验函数。
    """
    codecs = resolve_field_codecs(model, specs)
    required = _required_fields(specs)

    async def validate_fn(db: Any, df: Any, *, allow_overwrite: bool = False) -> tuple[Any, list[dict[str, Any]]]:
        pl = _require_polars()
        errors: list[dict[str, Any]] = []
        collector = ErrorCollector(errors)
        valid_rows: list[dict[str, Any]] = []
        rows = df.to_dicts() if not df.is_empty() else []
        for row in rows:
            row_number = int(row.get("row_number") or 0)
            parsed: dict[str, Any] = {"row_number": row_number}
            has_error = False
            for spec in specs:
                field = spec.name
                raw = row.get(field)
                raw_text = str(raw).strip() if raw is not None else ""
                if raw is None or raw_text == "":
                    if field in required:
                        collector.add(
                            row_number=row_number,
                            field=field,
                            message=f"Missing required field {field} / 缺少必填字段 {field}",
                            type="required",
                        )
                        has_error = True
                    parsed[field] = None
                    continue
                codec = codecs.get(field)
                if codec is not None:
                    try:
                        parsed[field] = codec.parse(raw_text)
                    except Exception:
                        collector.add(
                            row_number=row_number,
                            field=field,
                            message=f"Invalid value for {field}: {raw_text} / 字段 {field} 格式错误: {raw_text}",
                            type="format",
                            value=raw_text,
                        )
                        has_error = True
                    continue
                try:
                    parsed[field] = cast_basic(raw_text, spec.python_type)
                except Exception:
                    collector.add(
                        row_number=row_number,
                        field=field,
                        message=f"Invalid value for {field}: {raw_text} / 字段 {field} 格式错误: {raw_text}",
                        type="format",
                        value=raw_text,
                    )
                    has_error = True
            if not has_error:
                valid_rows.append(parsed)

        if unique_fields and not allow_overwrite and valid_rows:
            db_errors, valid_rows = await _check_db_unique(
                db=db,
                model=model,
                unique_fields=unique_fields,
                rows=valid_rows,
            )
            errors.extend(db_errors)

        valid_df = pl.DataFrame(valid_rows) if valid_rows else pl.DataFrame()
        return valid_df, errors

    return validate_fn


def _build_persist_fn(*, model: Any) -> Any:
    """Build and return a persistence function for SQLAlchemy insert operations.
    构建并返回用于 SQLAlchemy 插入操作的持久化函数。

    The returned `persist_fn` will accept (db, valid_df, *, allow_overwrite=False)
    and perform bulk insert of validated rows.
    返回的 `persist_fn` 接受 (db, valid_df, *, allow_overwrite=False) 并对校验通过的行进行批量插入。

    Args:
        model: SQLAlchemy model class to insert into.
            要插入的 SQLAlchemy 模型类。

    Returns:
        Callable: An async persistence function that returns number of written rows.
            异步持久化函数，返回写入的行数。
    """

    async def persist_fn(db: Any, valid_df: Any, *, allow_overwrite: bool = False) -> int:
        rows = valid_df.to_dicts() if not valid_df.is_empty() else []
        for row in rows:
            row.pop("row_number", None)
        if not rows:
            return 0
        sa = _require_sqlalchemy()
        stmt = sa.insert(model)
        await db.execute(stmt, rows)
        commit = getattr(db, "commit", None)
        if callable(commit):
            result = commit()
            if inspect.isawaitable(result):
                await result
        return len(rows)

    return persist_fn


async def import_model_csv(
    file: UploadFile,
    *,
    model: Any,
    db: Any,
    unique_fields: list[str] | None = None,
    columns: list[str] | None = None,
    options: ImportOptions | None = None,
    persist_fn: Any | None = None,
) -> ImportResult[ImportErrorItem]:
    """Import a CSV file into a SQLAlchemy ORM model.
    使用 SQLAlchemy ORM 将 CSV 文件导入模型。

    This helper wires together parsing, validation (including DB-uniqueness
    checks) and persistence for SQLAlchemy models using the package's
    import/export primitives.
    该工具将解析、校验（包括数据库唯一性检查）和持久化组合在一起，供 SQLAlchemy 模型使用库的导入/导出原语。

    Args:
        file: Uploaded CSV file (`fastapi.UploadFile`).
            上传的 CSV 文件（`fastapi.UploadFile`）。
        model: SQLAlchemy model class to import into.
            要导入的 SQLAlchemy 模型类。
        db: Asynchronous DB session/connection to use for checks and persistence.
            用于校验和持久化的异步数据库会话/连接。
        unique_fields: Optional list of fields that must be unique in DB.
            可选：需在数据库中唯一的字段列表。
        columns: Optional list of column names to import; defaults to resolved import specs.
            可选：要导入的列名列表；默认使用解析后的导入规范。
        options: Optional import options.
            可选的导入配置选项。
        persist_fn: Optional custom persistence function; if omitted, the default
            SQLAlchemy-based persist function will be used.
            可选：自定义持久化函数；若省略，将使用默认基于 SQLAlchemy 的持久化函数。

    Returns:
        ImportResult: Result object with status, imported_rows and errors if any.
            返回 ImportResult，包含状态、导入行数和（如有）错误列表。

    Raises:
        ImportExportError: When required parameters are missing or validation fails.
            当缺少必需参数或校验失败时抛出 ImportExportError。
    """
    if db is None:
        raise ImportExportError(message="db is required / 必须提供 db")
    opts = options or ImportOptions()
    effective_unique_fields = unique_fields if unique_fields is not None else opts.unique_fields
    specs = resolve_import_specs(get_field_specs(model), columns)
    validate_fn = _build_validate_fn(model=model, specs=specs, unique_fields=effective_unique_fields)
    persist_fn_final = persist_fn or _build_persist_fn(model=model)
    svc = ImportExportService(db=db)
    allow_exts = CSV_ALLOWED_EXTENSIONS if opts.allowed_extensions is None else opts.allowed_extensions
    allow_mimes = CSV_ALLOWED_MIME_TYPES if opts.allowed_mime_types is None else opts.allowed_mime_types
    validate_resp = await svc.upload_parse_validate(
        file=file,
        column_aliases=_build_column_aliases(specs),
        validate_fn=validate_fn,
        allow_overwrite=opts.allow_overwrite,
        unique_fields=effective_unique_fields,
        db_checks=opts.db_checks,
        allowed_extensions=allow_exts,
        allowed_mime_types=allow_mimes,
    )
    if validate_resp.errors:
        return ImportResult(status=ImportStatus.VALIDATED, imported_rows=0, errors=validate_resp.errors)
    commit = await svc.commit(
        body=ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            allow_overwrite=opts.allow_overwrite,
        ),
        persist_fn=persist_fn_final,
    )
    return ImportResult(status=ImportStatus.COMMITTED, imported_rows=commit.imported_rows, errors=[])
