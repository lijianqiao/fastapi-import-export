"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: export_model.py
@DateTime: 2026-02-09
@Docs: SQLAlchemy CSV export adapter.
SQLAlchemy CSV 导出适配器。
"""

from typing import Any

from fastapi_import_export.contrib.sqlalchemy.adapters import (
    _require_sqlalchemy,
    get_field_specs,
    resolve_export_specs,
    resolve_field_codecs,
)
from fastapi_import_export.easy import export_csv
from fastapi_import_export.exporter import ExportPayload
from fastapi_import_export.options import ExportOptions


def _apply_filters(stmt: Any, *, model: Any, filters: Any) -> Any:
    if filters is None:
        return stmt
    if callable(filters):
        expr = filters(model)
        if expr is None:
            return stmt
        if isinstance(expr, (list, tuple, set)):
            for item in expr:
                stmt = stmt.where(item)
            return stmt
        return stmt.where(expr)
    for field, value in filters.items():
        col = getattr(model, field, None)
        if col is None:
            continue
        if isinstance(value, (list, tuple, set)):
            stmt = stmt.where(col.in_(list(value)))
        else:
            stmt = stmt.where(col == value)
    return stmt


async def export_model_csv(
    *,
    model: Any,
    db: Any,
    filters: dict[str, object] | None = None,
    columns: list[str] | None = None,
    options: ExportOptions | None = None,
) -> ExportPayload:
    """Export ORM model rows to CSV using SQLAlchemy async session.
    使用 SQLAlchemy 异步会话导出 CSV。
    """
    sa = _require_sqlalchemy()
    columns_final = columns if columns is not None else (options.columns if options else None)
    specs = resolve_export_specs(get_field_specs(model), columns_final)
    codecs = resolve_field_codecs(model, specs)
    stmt = _apply_filters(sa.select(model), model=model, filters=filters)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    data: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for spec in specs:
            value = getattr(row, spec.name, None)
            codec = codecs.get(spec.name)
            item[spec.name] = codec.format(value) if codec is not None else value
        data.append(item)

    filename = options.filename if options else None
    effective_options = ExportOptions(
        filename=filename or f"{model.__name__.lower()}.csv",
        media_type=options.media_type if options else None,
        include_bom=options.include_bom if options else False,
        line_ending=options.line_ending if options else "\r\n",
        chunk_size=options.chunk_size if options else 64 * 1024,
        columns=[spec.name for spec in specs],
    )
    return await export_csv(data, options=effective_options)
