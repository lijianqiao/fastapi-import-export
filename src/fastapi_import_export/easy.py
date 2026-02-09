"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: easy.py
@DateTime: 2026-02-09
@Docs: Easy-layer API for import/export.
易用层 API：零配置 / 显式配置入口。
"""

import inspect
from collections.abc import Iterable, Mapping
from typing import Any

from fastapi import UploadFile

from fastapi_import_export.codecs import Codec
from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.exporter import ExportPayload
from fastapi_import_export.formats import (
    CSV_ALLOWED_EXTENSIONS,
    CSV_ALLOWED_MIME_TYPES,
    XLSX_ALLOWED_EXTENSIONS,
    XLSX_ALLOWED_MIME_TYPES,
    ExportFormat,
    extension_for,
    media_type_for,
)
from fastapi_import_export.importer import ImportResult, ImportStatus
from fastapi_import_export.options import ExportOptions, ImportOptions
from fastapi_import_export.renderers import render_chunks
from fastapi_import_export.resource import Resource
from fastapi_import_export.schemas import ImportCommitRequest, ImportErrorItem
from fastapi_import_export.serializers import CsvSerializer, XlsxSerializer
from fastapi_import_export.service import ImportExportService


async def export_csv(
    source: Any,
    *,
    resource: type[Resource] | None = None,
    params: Any | None = None,
    options: ExportOptions | None = None,
) -> ExportPayload:
    """Export data to CSV with sensible defaults.
    以合理默认值导出 CSV。

    Args:
        source: Data source (iterable rows, DataFrame, or query function).
            数据源（可迭代行、DataFrame 或查询函数）。
        resource: Optional Resource class for field mapping.
            可选的用于字段映射的 Resource 类。
        params: Optional parameters to pass to query function if source is callable.
            如果 source 可调用，传递给查询函数的可选参数。
        options: Optional ExportOptions to override defaults.
            可选的 ExportOptions，用于覆盖默认值。
    Returns:
        ExportPayload: Payload containing filename, media type, and byte stream.
            包含文件名、媒体类型和字节流的导出负载。

    """
    return await _export(
        source,
        fmt=ExportFormat.CSV,
        resource=resource,
        params=params,
        options=options,
    )


async def export_xlsx(
    source: Any,
    *,
    resource: type[Resource] | None = None,
    params: Any | None = None,
    options: ExportOptions | None = None,
) -> ExportPayload:
    """Export data to XLSX with sensible defaults.
    以合理默认值导出 XLSX。

    Args:
        source: Data source (iterable rows, DataFrame, or query function).
            数据源（可迭代行、DataFrame 或查询函数）。
        resource: Optional Resource class for field mapping.
            可选的用于字段映射的 Resource 类。
        params: Optional parameters to pass to query function if source is callable.
            如果 source 可调用，传递给查询函数的可选参数。
        options: Optional ExportOptions to override defaults.
            可选的 ExportOptions，用于覆盖默认值。
    Returns:
        ExportPayload: Payload containing filename, media type, and byte stream.
            包含文件名、媒体类型和字节流的导出负载。

    """
    return await _export(
        source,
        fmt=ExportFormat.XLSX,
        resource=resource,
        params=params,
        options=options,
    )


async def import_csv(
    file: UploadFile,
    *,
    resource: type[Resource],
    validate_fn: Any,
    persist_fn: Any,
    options: ImportOptions | None = None,
) -> ImportResult[ImportErrorItem]:
    """Import CSV using the built-in workflow.
    使用内置流程导入 CSV。

    Args:
        file: Uploaded CSV file.
            上传的 CSV 文件。
        resource: Resource class for field mapping.
            用于字段映射的 Resource 类。
        validate_fn: Function to validate imported data.
            用于验证导入数据的函数。
        persist_fn: Function to persist validated data.
            用于持久化验证数据的函数。
        options: Optional ImportOptions to override defaults.
            可选的 ImportOptions，用于覆盖默认值。
    Returns:
        ImportResult: Result of the import process, including status, imported rows count, and errors if any.
            导入过程的结果，包括状态、导入行数和错误（如果有）。

    """
    opts = options or ImportOptions()
    return await _import_file(
        file=file,
        resource=resource,
        validate_fn=validate_fn,
        persist_fn=persist_fn,
        options=opts,
        allowed_extensions=CSV_ALLOWED_EXTENSIONS if opts.allowed_extensions is None else opts.allowed_extensions,
        allowed_mime_types=CSV_ALLOWED_MIME_TYPES if opts.allowed_mime_types is None else opts.allowed_mime_types,
    )


async def import_xlsx(
    file: UploadFile,
    *,
    resource: type[Resource],
    validate_fn: Any,
    persist_fn: Any,
    options: ImportOptions | None = None,
) -> ImportResult[ImportErrorItem]:
    """Import file using the built-in workflow.
    使用内置流程导入文件。

    Args:
        file: Uploaded XLSX file.
            上传的 XLSX 文件。
        resource: Resource class for field mapping.
            用于字段映射的 Resource 类。
        validate_fn: Function to validate imported data.
            用于验证导入数据的函数。
        persist_fn: Function to persist validated data.
            用于持久化验证数据的函数。
        options: Optional ImportOptions to override defaults.
            可选的 ImportOptions，用于覆盖默认值。
    Returns:
        ImportResult: Result of the import process, including status, imported rows count, and errors if any.
            导入过程的结果，包括状态、导入行数和错误（如果有）。

    """
    opts = options or ImportOptions()
    return await _import_file(
        file=file,
        resource=resource,
        validate_fn=validate_fn,
        persist_fn=persist_fn,
        options=opts,
        allowed_extensions=XLSX_ALLOWED_EXTENSIONS if opts.allowed_extensions is None else opts.allowed_extensions,
        allowed_mime_types=XLSX_ALLOWED_MIME_TYPES if opts.allowed_mime_types is None else opts.allowed_mime_types,
    )


async def _export(
    source: Any,
    *,
    fmt: ExportFormat,
    resource: type[Resource] | None,
    params: Any | None,
    options: ExportOptions | None,
) -> ExportPayload:
    """Export data to specified format with sensible defaults.
    以合理默认值导出指定格式的数据。

    Args:
        source: Data source (iterable rows, DataFrame, or query function).
            数据源（可迭代行、DataFrame 或查询函数）。
        fmt: Export format (e.g., 'csv' or 'xlsx').
            导出格式（例如 'csv' 或 'xlsx'）。
        resource: Optional Resource class for field mapping.
            可选的用于字段映射的 Resource 类。
        params: Optional parameters to pass to query function if source is callable.
            如果 source 可调用，传递给查询函数的可选参数。
        options: Optional ExportOptions to override defaults.
            可选的 ExportOptions，用于覆盖默认值。
    Returns:
        ExportPayload: Payload containing filename, media type, and byte stream.
            包含文件名、媒体类型和字节流的导出负载。

    """
    opts = options or ExportOptions()
    data = await _resolve_source(source, resource=resource, params=params)
    rows, output_columns = _normalize_rows(data, resource=resource, columns=opts.columns)
    serializer = CsvSerializer() if fmt == ExportFormat.CSV else XlsxSerializer()
    effective_options = ExportOptions(
        filename=opts.filename,
        media_type=opts.media_type,
        include_bom=opts.include_bom,
        line_ending=opts.line_ending,
        chunk_size=opts.chunk_size,
        columns=output_columns,
    )
    payload_bytes = serializer.serialize(data=rows, options=effective_options)
    stream = render_chunks(payload_bytes, chunk_size=opts.chunk_size)
    filename = opts.filename or _default_filename(fmt=fmt, resource=resource)
    media_type = opts.media_type or media_type_for(fmt)
    return ExportPayload(filename=filename, media_type=media_type, stream=stream)


async def _import_file(
    *,
    file: UploadFile,
    resource: type[Resource],
    validate_fn: Any,
    persist_fn: Any,
    options: ImportOptions,
    allowed_extensions: Iterable[str],
    allowed_mime_types: Iterable[str],
) -> ImportResult[ImportErrorItem]:
    """Import file using the built-in workflow.
    使用内置流程导入文件。

    Args:
        file: Uploaded file.
            上传的文件。
        resource: Resource class for field mapping.
            用于字段映射的 Resource 类。
        validate_fn: Function to validate imported data.
            用于验证导入数据的函数。
        persist_fn: Function to persist validated data.
            用于持久化验证数据的函数。
        options: ImportOptions to override defaults.
            用于覆盖默认值的 ImportOptions。
        allowed_extensions: Allowed file extensions for validation.
            验证允许的文件扩展名。
        allowed_mime_types: Allowed MIME types for validation.
            验证允许的 MIME 类型。
    Returns:
        ImportResult: Result of the import process, including status, imported rows count, and errors if any.
            导入过程的结果，包括状态、导入行数和错误（如果有）。
    """
    svc = ImportExportService(db=options.db)
    codecs = resource.field_codecs if resource is not None else {}

    async def wrapped_validate_fn(db, df, *, allow_overwrite: bool = False):
        if not codecs:
            return await validate_fn(db, df, allow_overwrite=allow_overwrite)
        decoded_df, decode_errors = _decode_df_with_codecs(df, codecs)
        valid_df, errors = await validate_fn(db, decoded_df, allow_overwrite=allow_overwrite)
        encoded_df = _encode_df_with_codecs(valid_df, codecs)
        return encoded_df, decode_errors + errors

    async def wrapped_persist_fn(db, valid_df, *, allow_overwrite: bool = False):
        if not codecs:
            return await persist_fn(db, valid_df, allow_overwrite=allow_overwrite)
        decoded_df, decode_errors = _decode_df_with_codecs(valid_df, codecs)
        if decode_errors:
            raise ImportExportError(
                message="Codec parse failed during commit / Codec 解析失败",
                details=decode_errors[:50],
            )
        return await persist_fn(db, decoded_df, allow_overwrite=allow_overwrite)

    validate_resp = await svc.upload_parse_validate(
        file=file,
        column_aliases=resource.field_mapping(),
        validate_fn=wrapped_validate_fn,
        allow_overwrite=options.allow_overwrite,
        unique_fields=options.unique_fields,
        db_checks=options.db_checks,
        allowed_extensions=allowed_extensions,
        allowed_mime_types=allowed_mime_types,
    )
    if validate_resp.errors:
        return ImportResult(status=ImportStatus.VALIDATED, imported_rows=0, errors=validate_resp.errors)
    commit = await svc.commit(
        body=ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            allow_overwrite=options.allow_overwrite,
        ),
        persist_fn=wrapped_persist_fn,
    )
    return ImportResult(status=ImportStatus.COMMITTED, imported_rows=commit.imported_rows, errors=[])


async def _resolve_source(source: Any, *, resource: type[Resource] | None, params: Any | None) -> Any:
    """Resolve the data source, calling it if it's a callable.
    解析数据源，如果是可调用的则调用它。

    Args:
        source: Data source (iterable rows, DataFrame, or query function).
            数据源（可迭代行、DataFrame 或查询函数）。
        resource: Optional Resource class for field mapping.
            可选的用于字段映射的 Resource 类。
        params: Optional parameters to pass to query function if source is callable.
            如果 source 可调用，传递给查询函数的可选参数。
    Returns:
        Any: Resolved data from the source.
            来自数据源的解析数据。

    """
    if callable(source):
        return await _call_query_fn(source, resource=resource, params=params)
    return source


async def _call_query_fn(fn: Any, *, resource: type[Resource] | None, params: Any | None) -> Any:
    """Call the query function with optional resource and params.
    调用查询函数，可选地传递 resource 和 params。

    Args:
        fn: Query function to call.
            要调用的查询函数。
        resource: Optional Resource class for field mapping.
            可选的用于字段映射的 Resource 类。
        params: Optional parameters to pass to the query function.
            可选的参数，传递给查询函数。
    Returns:
        Any: Result from the query function.
            查询函数的结果。
    """
    sig = inspect.signature(fn)
    kwargs: dict[str, Any] = {}
    if _accepts_kw(sig, "resource"):
        kwargs["resource"] = resource
    if _accepts_kw(sig, "params"):
        kwargs["params"] = params
    result = fn(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _accepts_kw(sig: inspect.Signature, name: str) -> bool:
    """Check if the function signature accepts a keyword argument.
    检查函数签名是否接受某个关键字参数。

    Args:
        sig: Function signature to check.
            要检查的函数签名。
        name: Name of the keyword argument to look for.
            要查找的关键字参数名称。
    Returns:
        bool: True if the function accepts the keyword argument, False otherwise.
            如果函数接受该关键字参数则返回 True，否则返回 False。
    """
    if name in sig.parameters:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _normalize_rows(
    data: Any,
    *,
    resource: type[Resource] | None,
    columns: list[str] | None,
) -> tuple[list[dict[str, Any]], list[str] | None]:
    """Normalize the data into a list of dict rows and determine output columns.
    将数据规范化为字典行列表，并确定输出列。

    Args:
        data: Input data (iterable rows or DataFrame).
            输入数据（可迭代行或 DataFrame）。
        resource: Optional Resource class for field mapping.
            可选的用于字段映射的 Resource 类。
        columns: Optional list of columns to include in the output.
            可选的要包含在输出中的列列表。
    Returns:
        tuple: A tuple containing the list of normalized rows and the list of output columns.
            包含规范化行列表和输出列列表的元组。
    """
    rows = _to_rows(data, resource=resource)
    mapping = resource.export_mapping() if resource is not None else {}
    ordered = columns or (resource.field_order() if resource is not None else _infer_columns(rows))
    codecs = resource.field_codecs if resource is not None else {}
    output_columns = [mapping.get(col, col) for col in ordered]
    output: list[dict[str, Any]] = []
    for row in rows:
        out: dict[str, Any] = {}
        for col in ordered:
            value = row.get(col)
            codec = codecs.get(col)
            if codec is not None:
                value = codec.format(value)
            out[mapping.get(col, col)] = value
        output.append(out)
    return output, output_columns


def _to_rows(data: Any, *, resource: type[Resource] | None) -> list[dict[str, Any]]:
    """Convert input data to a list of dict rows.
    将输入数据转换为字典行列表。

    Args:
        data: Input data (iterable rows or DataFrame).
            输入数据（可迭代行或 DataFrame）。
    Returns:
        list[dict[str, Any]]: List of dict rows.
            字典行列表。
    """
    if _is_polars_df(data):
        return data.to_dicts()
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, (str, bytes)):
        raise TypeError("export source must be iterable rows or DataFrame / 导出源必须是可迭代行或 DataFrame")
    if isinstance(data, Iterable):
        rows: list[dict[str, Any]] = []
        for item in data:
            rows.append(_coerce_row(item, resource=resource))
        return rows
    raise TypeError("export source must be iterable rows or DataFrame / 导出源必须是可迭代行或 DataFrame")


def _coerce_row(item: Any, *, resource: type[Resource] | None) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    if resource is not None:
        fields = resource.field_order()
        if not fields:
            raise TypeError("resource has no fields; cannot export object rows / 资源未定义字段，无法导出对象行")
        return {field: getattr(item, field, None) for field in fields}
    raise TypeError("export rows must be mappings unless resource is provided / 导出行必须是映射，除非提供 resource")


def _decode_df_with_codecs(df: Any, codecs: dict[str, Codec]) -> tuple[Any, list[dict[str, Any]]]:
    import polars as pl

    rows = df.to_dicts() if not df.is_empty() else []
    decoded_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in rows:
        row_number = int(row.get("row_number") or 0)
        decoded: dict[str, Any] = dict(row)
        decoded["row_number"] = row_number
        has_error = False
        for field, codec in codecs.items():
            if field not in row:
                continue
            raw = row.get(field)
            raw_text = "" if raw is None else str(raw).strip()
            try:
                decoded[field] = codec.parse(raw_text)
            except Exception:
                errors.append(
                    {
                        "row_number": row_number,
                        "field": field,
                        "message": f"Invalid value for {field}: {raw_text} / 字段 {field} 格式错误: {raw_text}",
                        "type": "format",
                        "value": raw_text,
                    }
                )
                has_error = True
        if not has_error:
            decoded_rows.append(decoded)
    decoded_df = pl.DataFrame(decoded_rows) if decoded_rows else pl.DataFrame()
    return decoded_df, errors


def _encode_df_with_codecs(df: Any, codecs: dict[str, Codec]) -> Any:
    import polars as pl

    rows = df.to_dicts() if not df.is_empty() else []
    encoded_rows: list[dict[str, Any]] = []
    for row in rows:
        encoded: dict[str, Any] = dict(row)
        for field, codec in codecs.items():
            if field not in row:
                continue
            encoded[field] = codec.format(row.get(field))
        encoded_rows.append(encoded)
    return pl.DataFrame(encoded_rows) if encoded_rows else pl.DataFrame()


def _is_polars_df(value: Any) -> bool:
    try:
        import polars as pl  # type: ignore
    except Exception:
        return False
    return isinstance(value, pl.DataFrame)


def _infer_columns(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Infer column names from an iterable of mapping rows.
    从映射行的可迭代对象中推断列名。

    Args:
        rows: Iterable of mapping rows.
            映射行的可迭代对象。
    Returns:
        list[str]: List of inferred column names.
            推断的列名列表。
    """
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                columns.append(k)
    return columns


def _default_filename(*, fmt: ExportFormat, resource: type[Resource] | None) -> str:
    """Generate a default filename based on the resource name and export format.
    根据资源名称和导出格式生成默认文件名。

    Args:
        fmt: Export format.
            导出格式。
        resource: Optional Resource class.
            可选的资源类。
    Returns:
        str: Default filename.
            默认文件名。
    """
    base = resource.__name__.lower() if resource is not None else "export"
    return f"{base}{extension_for(fmt)}"
