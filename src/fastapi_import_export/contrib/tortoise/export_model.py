"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: export_model.py
@DateTime: 2026-02-09
@Docs: Tortoise ORM CSV export adapter.
Tortoise ORM CSV 导出适配器。
"""

from typing import Any

from fastapi_import_export.contrib.tortoise.adapters import (
    get_field_specs,
    resolve_export_specs,
    resolve_field_codecs,
)
from fastapi_import_export.easy import export_csv
from fastapi_import_export.exporter import ExportPayload
from fastapi_import_export.options import ExportOptions


async def export_model_csv(
    *,
    model: Any,
    filters: dict[str, object] | None = None,
    columns: list[str] | None = None,
    options: ExportOptions | None = None,
) -> ExportPayload:
    """Export ORM model rows to CSV using Tortoise ORM.
    使用 Tortoise ORM 导出 CSV。

    Args:
        model: Tortoise model class.
            Tortoise 模型类。
        filters: Optional filter mapping or callable, applied to a queryset.
            可选：用于过滤的映射或可调用，会应用到 queryset 上。
        columns: Optional list of columns to include.
            可选：要包含的列名列表。
        options: Optional `ExportOptions` to override defaults.
            可选的 `ExportOptions`，用于覆盖默认导出设置。

    Returns:
        ExportPayload: Export result with filename, media type and byte stream.
            导出结果，包含文件名、媒体类型与字节流。
    """
    columns_final = columns if columns is not None else (options.columns if options else None)
    specs = resolve_export_specs(get_field_specs(model), columns_final)
    codecs = resolve_field_codecs(model, specs)
    if filters is None:
        queryset = model.all()
    elif callable(filters):
        expr = filters(model)
        if isinstance(expr, dict):
            queryset = model.filter(**expr)
        else:
            queryset = model.filter(expr)
    else:
        kwargs: dict[str, object] = {}
        for field, value in filters.items():
            if isinstance(value, (list, tuple, set)):
                kwargs[f"{field}__in"] = list(value)
            else:
                kwargs[field] = value
        queryset = model.filter(**kwargs)

    field_names = [spec.name for spec in specs]
    rows = await queryset.values(*field_names) if field_names else await queryset.values()
    data: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for spec in specs:
            value = row.get(spec.name)
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
        columns=field_names,
    )
    return await export_csv(data, options=effective_options)
