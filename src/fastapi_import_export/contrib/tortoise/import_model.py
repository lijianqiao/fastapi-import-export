"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: import_model.py
@DateTime: 2026-02-09
@Docs: Tortoise ORM CSV import adapter.
Tortoise ORM CSV 导入适配器。
"""

from typing import Any

from fastapi import UploadFile

from fastapi_import_export.contrib.tortoise.adapters import (
    FieldSpec,
    _require_polars,
    _require_tortoise,
    cast_basic,
    get_field_specs,
    resolve_field_codecs,
    resolve_import_specs,
)
from fastapi_import_export.formats import CSV_ALLOWED_EXTENSIONS, CSV_ALLOWED_MIME_TYPES
from fastapi_import_export.importer import ImportResult, ImportStatus
from fastapi_import_export.options import ImportOptions
from fastapi_import_export.schemas import ImportCommitRequest, ImportErrorItem
from fastapi_import_export.service import ImportExportService
from fastapi_import_export.validation_core import ErrorCollector


def _build_column_aliases(specs: list[FieldSpec]) -> dict[str, str]:
    """Build column alias mapping for Tortoise import.
    为 Tortoise 导入构建列别名映射。

    Args:
        specs: Field specification list.
            字段规范列表。
    Returns:
        dict[str, str]: Column name -> alias mapping.
            列名到别名的映射。
    """
    return {spec.name: spec.name for spec in specs}


def _required_fields(specs: list[FieldSpec]) -> set[str]:
    """Compute required field names for Tortoise import.
    计算 Tortoise 导入的必填字段名称集合。

    Args:
        specs: Field specification list.
            字段规范列表。
    Returns:
        set[str]: Required field names.
            必填字段名称集合。
    """
    required: set[str] = set()
    for spec in specs:
        if spec.nullable:
            continue
        if spec.has_default:
            continue
        if spec.primary_key and spec.generated:
            continue
        required.add(spec.name)
    return required


async def _check_db_unique(
    *,
    model: Any,
    unique_fields: list[str],
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Check for existing records in the DB that conflict with unique fields (Tortoise).
    检查数据库中是否存在与唯一字段冲突的记录（Tortoise 版本）。

    Uses Tortoise query APIs to find existing values and returns (errors, filtered_rows).
    使用 Tortoise 查询 API 查找已存在值，返回 (errors, filtered_rows)。

    Args:
        model: Tortoise model class.
            Tortoise 模型类。
        unique_fields: Fields to consider for uniqueness.
            用于唯一性判断的字段列表。
        rows: Candidate rows with `row_number` for error reporting.
            带有 `row_number` 的候选行，用于错误定位。

    Returns:
        Tuple of (errors, filtered_rows).
            (错误列表, 过滤后的行列表)。
    """
    _require_tortoise()
    from tortoise.expressions import Q

    fields = [f for f in unique_fields if f]
    if not fields:
        return [], rows

    key_to_rows: dict[tuple[Any, ...], list[int]] = {}
    for row in rows:
        key = tuple(row.get(f) for f in fields)
        if any(part is None or (isinstance(part, str) and not part.strip()) for part in key):
            continue
        key_to_rows.setdefault(key, []).append(int(row.get("row_number") or 0))

    keys = list(key_to_rows.keys())
    if not keys:
        return [], rows

    existing: set[tuple[Any, ...]] = set()
    if len(fields) == 1:
        values = [k[0] for k in keys]
        existing_values = await model.filter(**{f"{fields[0]}__in": values}).values_list(fields[0], flat=True)
        existing = {(v,) for v in existing_values}
    else:
        query = None
        for key in keys:
            cond = Q(**dict(zip(fields, key, strict=True)))
            query = cond if query is None else (query | cond)
        if query is not None:
            existing_rows = await model.filter(query).values_list(*fields)
            existing = {tuple(r) for r in existing_rows}

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
    """Build validation function for Tortoise model import.
    构建用于 Tortoise 模型导入的校验函数。

    Returns a callable `async def validate_fn(db, df, *, allow_overwrite=False)`
    that returns (valid_df, errors).
    返回可调用的 `async def validate_fn(db, df, *, allow_overwrite=False)`，其返回 (valid_df, errors)。

    Args:
        model: Tortoise model class.
            Tortoise 模型类。
        specs: Field specifications.
            字段规范列表。
        unique_fields: Optional unique fields to check against DB.
            可选：用于数据库校验的唯一字段列表。

    Returns:
        Callable: The async validation function.
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
            db_errors, valid_rows = await _check_db_unique(model=model, unique_fields=unique_fields, rows=valid_rows)
            errors.extend(db_errors)

        valid_df = pl.DataFrame(valid_rows) if valid_rows else pl.DataFrame()
        return valid_df, errors

    return validate_fn


def _build_persist_fn(*, model: Any) -> Any:
    """Build a persistence function that bulk-creates model instances (Tortoise).
    构建用于批量创建模型实例的持久化函数（Tortoise）。

    The returned `persist_fn` accepts (db, valid_df, *, allow_overwrite=False)
    and uses Tortoise `bulk_create` to persist rows.
    返回的 `persist_fn` 接受 (db, valid_df, *, allow_overwrite=False)，并使用 Tortoise 的 `bulk_create` 持久化行。

    Args:
        model: Tortoise model class.
            Tortoise 模型类。

    Returns:
        Callable: Async persistence function returning number of created rows.
            异步持久化函数，返回创建的行数。
    """

    async def persist_fn(db: Any, valid_df: Any, *, allow_overwrite: bool = False) -> int:
        rows = valid_df.to_dicts() if not valid_df.is_empty() else []
        for row in rows:
            row.pop("row_number", None)
        if not rows:
            return 0
        objs = [model(**row) for row in rows]
        await model.bulk_create(objs)
        return len(rows)

    return persist_fn


async def import_model_csv(
    file: UploadFile,
    *,
    model: Any,
    unique_fields: list[str] | None = None,
    columns: list[str] | None = None,
    options: ImportOptions | None = None,
    persist_fn: Any | None = None,
) -> ImportResult[ImportErrorItem]:
    """Import a CSV file into a Tortoise ORM model.
    使用 Tortoise ORM 将 CSV 文件导入模型。

    Args:
        file: Uploaded CSV file (`fastapi.UploadFile`).
            上传的 CSV 文件（`fastapi.UploadFile`）。
        model: Tortoise model class to import into.
            要导入的 Tortoise 模型类。
        unique_fields: Optional list of unique fields to check against DB.
            可选：需在数据库中校验唯一性的字段列表。
        columns: Optional list of columns to import.
            可选：要导入的列名列表。
        options: Optional import options.
            可选的导入配置选项。
        persist_fn: Optional custom persistence function; defaults to Tortoise bulk create.
            可选：自定义持久化函数；默认使用 Tortoise 的批量创建。

    Returns:
        ImportResult: Result object with status, imported_rows and errors.
            返回 ImportResult，包含状态、导入行数与错误列表（如有）。

    Raises:
        ImportExportError: If required setup is missing or operation fails.
            当缺少必要配置或操作失败时抛出 ImportExportError。
    """
    opts = options or ImportOptions()
    effective_unique_fields = unique_fields if unique_fields is not None else opts.unique_fields
    specs = resolve_import_specs(get_field_specs(model), columns)
    validate_fn = _build_validate_fn(model=model, specs=specs, unique_fields=effective_unique_fields)
    persist_fn_final = persist_fn or _build_persist_fn(model=model)
    svc = ImportExportService(db=opts.db)
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
