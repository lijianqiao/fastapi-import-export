---
name: fastapi-import-export
description: FastAPI-first import/export toolkit with composable workflows and optional backends.
---

# fastapi-import-export skill

## Description

This skill helps you build import and export workflows for FastAPI. It provides
an easy-layer API for 5-minute success, an explicit configuration layer for
common business needs, and an advanced hook-based layer for power users.

## Use Cases

- One-call CSV/XLSX import and export (easy layer).
- Explicit options for common business needs (options layer).
- Full hook-based lifecycle when you need custom pipelines (advanced layer).

## Core Concepts

- Resource: Field mapping and resource schema.
- Easy API: `export_*` / `import_*` top-level functions.
- Options: `ExportOptions` / `ImportOptions` (explicit configuration).
- Advanced API: Importer/Exporter/ImportExportService under `fastapi_import_export.advanced`.
- Facades: parse/storage/validation/db_validation optional backends.

## Capabilities

- Async-first APIs for FastAPI.
- Explicit field mapping to avoid ORM coupling.
- Optional dependencies with clear missing-dependency errors.
- Streaming export payloads.
- Defaults that reduce boilerplate (media_type, line endings, mapping).

## API Inventory

**Easy Layer (Top-level)**

- `export_csv(source, *, resource=None, params=None, options=None) -> ExportPayload`
- `export_xlsx(source, *, resource=None, params=None, options=None) -> ExportPayload`
- `import_csv(file, *, resource, validate_fn, persist_fn, options=None) -> ImportResult`
- `import_xlsx(file, *, resource, validate_fn, persist_fn, options=None) -> ImportResult`

**Options Layer**

- `ExportOptions`
	- `filename: str | None`
	- `media_type: str | None`
	- `include_bom: bool` (default: False)
	- `line_ending: str` (default: "\\r\\n")
	- `chunk_size: int` (default: 64 * 1024)
	- `columns: list[str] | None`
- `ImportOptions`
	- `db: Any | None`
	- `allow_overwrite: bool` (default: False)
	- `unique_fields: list[str] | None`
	- `db_checks: list[DbCheckSpec] | None`
	- `allowed_extensions: Iterable[str] | None`
	- `allowed_mime_types: Iterable[str] | None`

**Core Types**

- `Resource`
	- `field_aliases: dict[str, str]`
	- `field_mapping() -> dict[str, str]`
	- `export_aliases: dict[str, str]`
	- `export_mapping() -> dict[str, str]`
- `Importer`
	- `import_data(*, file, resource, allow_overwrite=False) -> ImportResult`
	- `parse(*, file, resource) -> TTable`
	- `validate(*, data, resource, allow_overwrite) -> tuple[TTable, list[TError]]`
	- `transform(*, data, resource) -> TTable`
	- `persist(*, data, resource, allow_overwrite) -> int`
- `Exporter`
	- `query(*, resource, params=None) -> TTable`
	- `serialize(*, data, fmt) -> bytes`
	- `render(*, data, fmt) -> ByteStream`
	- `stream(*, resource, fmt, filename, media_type, params=None) -> ExportPayload`
- `ImportExportService`
	- `upload_parse_validate(*, file, column_aliases, validate_fn, allow_overwrite=False, unique_fields=None, db_checks=None, allowed_extensions=None, allowed_mime_types=None) -> ImportValidateResponse`
	- `preview(*, import_id, checksum, page, page_size, kind) -> ImportPreviewResponse`
	- `commit(*, body, persist_fn, lock_namespace="import") -> ImportCommitResponse`

**Config and Facades**

- `resolve_config(...) -> ImportExportConfig`
- `parse_tabular_file(file_path, *, filename)`
- `normalize_columns(df, column_mapping)`
- `dataframe_to_preview_rows(df)`
- `collect_infile_duplicates(df, unique_fields)`
- `run_db_checks(*, db, df, specs, allow_overwrite=False)`

**Errors**

- `ImportExportError` with `message`, `status_code`, `details`, `error_code`
- `ParseError` / `ValidationError` / `PersistError` / `ExportError`

**ImportExportError error_code list (common)**

- `missing_dependency`: Optional backend dependency is not installed.
- `unsupported_media_type`: File extension or MIME type is not allowed.
- `import_export_error`: Default fallback code for generic errors.

## API Behavior Details

**Easy Export**

- `source` can be `Iterable[Mapping]`, `polars.DataFrame`, or `query_fn`.
- If `source` is callable, it is treated as `query_fn`.
- Column order: `options.columns` > `Resource` field order > inferred from rows.
- Column names: `Resource.export_mapping()` is applied.
- Defaults: `media_type` derived from format; CSV uses `\\r\\n` and no BOM.

**Easy Import**

- `import_csv/import_xlsx` runs upload -> parse -> validate -> commit.
- Requires `validate_fn` and `persist_fn` only.
- On validation errors returns `ImportResult(status=VALIDATED, errors=...)`.
- On success returns `ImportResult(status=COMMITTED, imported_rows=...)`.

**Importer.import_data**

- Required: `file`, `resource`
- Optional: `allow_overwrite`
- Returns: `ImportResult` with `status`, `imported_rows`, `errors`

**Exporter.stream**

- Required: `resource`, `fmt`, `filename`, `media_type`
- Optional: `params`
- Returns: `ExportPayload` with `filename`, `media_type`, `stream`

**ImportExportService.upload_parse_validate**

- Required: `file`, `column_aliases`, `validate_fn`
- Optional: `allow_overwrite`, `unique_fields`, `db_checks`, `allowed_extensions`, `allowed_mime_types`
- Returns: `ImportValidateResponse` with `import_id`, `checksum`, `total_rows`, `valid_rows`, `error_rows`, `errors`
- Errors:
	- 413 when upload exceeds `max_upload_mb`
	- 415 when extension or content type is not allowed
	- missing dependency errors for optional backends

**ImportExportService.preview**

- Required: `import_id` (UUID), `checksum`, `page`, `page_size`, `kind`
- `kind` is `all` or `valid`
- Returns: `ImportPreviewResponse` with `rows` (list of `ImportPreviewRow`)
- Errors:
	- 400 for invalid page/page_size/kind or checksum mismatch

**ImportExportService.commit**

- Required: `body`, `persist_fn`
- Optional: `lock_namespace`
- Returns: `ImportCommitResponse` with `imported_rows`, `status`, `created_at`
- Errors:
	- 400 for checksum empty/mismatch, invalid status, or validation errors
	- 409 when validated data is missing
	- 409 when Redis lock not acquired
	- DB integrity errors are mapped to user-friendly messages

## Field-level Response Structures

**ImportErrorItem**

```json
{
	"row_number": 12,
	"field": "email",
	"message": "Duplicate value for field email: a@b.com"
}
```

**ImportValidateResponse (partial)**

```json
{
	"import_id": "uuid",
	"checksum": "sha256",
	"total_rows": 100,
	"valid_rows": 95,
	"error_rows": 5,
	"errors": [
		{"row_number": 12, "field": "email", "message": "Duplicate value for field email: a@b.com"}
	]
}
```


## Key Configuration

- Upload allowlist via `resolve_config(allowed_extensions, allowed_mime_types)` or per-call override.
- Optional dependencies via extras: `[polars,xlsx,storage]` or `[full]`.
- Excel export uses `openpyxl` in easy layer.

## Example Snippets

**0) Easy Export (Top-level)**

```python
from fastapi import StreamingResponse
from fastapi_import_export import export_csv, Resource


class UserResource(Resource):
    id: int | None
    username: str


async def query_fn(*, resource, params=None):
    return [{"id": 1, "username": "alice"}]


payload = await export_csv(query_fn, resource=UserResource)
return StreamingResponse(payload.stream, media_type=payload.media_type)
```

**0.1) Easy Import (Top-level)**

```python
from fastapi_import_export import import_csv


async def validate_fn(db, df, *, allow_overwrite: bool = False):
    return df, []


async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
    return int(valid_df.height)


result = await import_csv(file, resource=UserResource, validate_fn=validate_fn, persist_fn=persist_fn)
```

**1) Define Resource and Importer**

```python
from fastapi_import_export.advanced import Importer, Resource


class UserResource(Resource):

    id: int | None
    username: str
    email: str

    field_aliases = {"Username": "username", "Email": "email"}


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)
```

**2) Streaming export**

```python
payload = await exporter.stream(
    resource=UserResource,
    fmt="csv",
    filename="users.csv",
    media_type="text/csv",
)
```

**2.1) Exporter module usage**

```python
import csv
import io
from collections.abc import AsyncIterator

from fastapi_import_export.advanced import Exporter, Resource


class UserResource(Resource):
	id: int | None
	username: str


async def query_fn(*, resource: type[Resource], params: dict | None = None):
	return [
		{"id": 1, "username": "alice"},
		{"id": 2, "username": "bob"},
	]


async def serialize_fn(*, data: list[dict], fmt: str) -> bytes:
	buf = io.StringIO()
	writer = csv.DictWriter(buf, fieldnames=["id", "username"])
	writer.writeheader()
	writer.writerows(data)
	return buf.getvalue().encode("utf-8-sig")


async def render_fn(*, data: bytes, fmt: str) -> AsyncIterator[bytes]:
	async def _stream() -> AsyncIterator[bytes]:
		yield data

	return _stream()


exporter = Exporter(query_fn=query_fn, serialize_fn=serialize_fn, render_fn=render_fn)
payload = await exporter.stream(
	resource=UserResource,
	fmt="csv",
	filename="users.csv",
	media_type="text/csv",
)
```

**3) Service workflow**

```python
from fastapi_import_export.advanced import ImportExportService


svc = ImportExportService(db=object())
resp = await svc.upload_parse_validate(
    file=file,
    column_aliases=UserResource.field_mapping(),
	validate_fn=service_validate_fn,
)
commit = await svc.commit(body=commit_body, persist_fn=service_persist_fn)
```

**4) Upload allowlist configuration**

```python
from fastapi_import_export.config import resolve_config


cfg = resolve_config(allowed_extensions=[".csv"], allowed_mime_types=["text/csv"])
svc = ImportExportService(db=object(), config=cfg)
```

## Advanced Extension Points

- `fastapi_import_export.advanced.Importer` for custom parse/validate/transform/persist.
- `fastapi_import_export.advanced.Exporter` for custom query/serialize/render.
- `fastapi_import_export.advanced.ImportExportService` for upload/preview/commit workflows.
- Facades: `parse`, `validation`, `db_validation`, `storage` to plug optional backends.

### Custom Serializer/Renderer

- **Serializer**: implement a function that turns table-like data into bytes.
  - Input: list[dict] or DataFrame (your choice)
  - Output: `bytes`
  - Use with `advanced.Exporter.serialize` or your own wrapper in the easy layer.
- **Renderer**: implement a function that turns bytes into `AsyncIterator[bytes]`.
  - Useful for chunking large payloads.

### Lifecycle Extension Rules

- Import lifecycle (advanced): `parse -> validate -> transform -> persist`
  - `validate` returns `(valid_data, errors)`. If `errors` is non-empty, skip transform/persist.
  - `allow_overwrite` is passed through to validation and persistence.
- Export lifecycle (advanced): `query -> serialize -> render`
  - `query` returns table-like data.
  - `serialize` returns bytes.
  - `render` returns an async byte stream.

### Optional Backends (Facades)

- `parse` and `validation` default to Polars backends when installed.
- `storage` defaults to filesystem storage when installed.
- Missing backend raises `ImportExportError(error_code="missing_dependency")`.

## Default Behaviors (Easy Layer)

- CSV default: no BOM, `\\r\\n` line endings.
- Media type: inferred from format.
- Column order: `options.columns` > `Resource` field order > inferred.
- Export mapping: `export_aliases` > invertible `field_aliases` > identity.

## Constraints

- Does not manage database connections.
- Does not own ORM, only adapts.
- Does not handle authentication or authorization.
