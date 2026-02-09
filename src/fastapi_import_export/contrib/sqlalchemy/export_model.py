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
    """
    Apply filters to a SQLAlchemy select statement based on the provided filters.
    根据提供的过滤器将过滤条件应用到 SQLAlchemy 的 select 语句上。

    Args:
        stmt: The initial SQLAlchemy select statement to apply filters to.
            要应用过滤器的初始 SQLAlchemy select 语句。
        model: The SQLAlchemy model class being queried, used to resolve column references.
            被查询的 SQLAlchemy 模型类，用于解析列引用。
        filters: Optional filters to apply. Can be a mapping of column->value,
            or a callable that accepts the model and returns an expression.
            可选的过滤器，可为列名到值的映射，或接收 model 并返回表达式的可调用对象。
    Returns:
        The SQLAlchemy statement with filters applied.
        应用过滤器后的 SQLAlchemy 语句。

    """
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
    """Export ORM model rows to CSV using a SQLAlchemy async session.
    使用 SQLAlchemy 异步会话导出 CSV。

    Export rows from a SQLAlchemy model into CSV format using sensible codecs
    inferred from the model and optional filtering/column selection.
    从 SQLAlchemy 模型导出行到 CSV，自动根据模型推断字段编解码器，并支持可选的过滤与字段选择。

    Args:
        model: SQLAlchemy model class.
            SQLAlchemy 模型类。
        db: Asynchronous database session/connection used to execute queries.
            异步数据库会话/连接，用于执行查询。
        filters: Optional filters to apply. Can be a mapping of column->value,
            or a callable that accepts the model and returns an expression.
            可选的过滤器，可为列名到值的映射，或接收 model 并返回表达式的可调用对象。
        columns: Optional list of columns to include; defaults to all exportable columns.
            可选的要包含的列名列表；默认导出所有可导出的列。
        options: Optional `ExportOptions` to override default export settings.
            可选的 `ExportOptions`，用于覆盖默认导出设置。

    Returns:
        ExportPayload: Contains filename, media_type and an async byte stream.
            包含文件名、媒体类型以及异步字节流的导出负载。

    Raises:
        ImportExportError: If SQLAlchemy is not available or the query fails.
            当无法使用 SQLAlchemy 或查询失败时抛出。
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
