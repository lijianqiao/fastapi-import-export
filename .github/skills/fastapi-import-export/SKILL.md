---
name: fastapi-import-export
description: FastAPI-first import/export toolkit with composable workflows and optional backends.
---

# fastapi-import-export skill

## Description

This skill helps you build import and export workflows for FastAPI. It provides
composable lifecycle hooks, optional backend facades, and streaming exports for
large datasets.

## Use Cases

- Upload files and run parse/validate/preview/commit.
- Export data to CSV/XLSX with streaming responses.
- Enable parsing/storage/validation backends only when needed.

## Core Concepts

- Resource: Field mapping and resource schema.
- Importer: Parse/validate/transform/persist lifecycle.
- Exporter: Query/serialize/render lifecycle.
- ImportExportService: End-to-end upload/preview/commit workflow.
- Facades: parse/storage/validation/db_validation optional backends.

## Capabilities

- Async-first APIs for FastAPI.
- Explicit field mapping to avoid ORM coupling.
- Optional dependencies with clear missing-dependency errors.
- Streaming export payloads.

## API Inventory

**Core Types**

- `Resource`
	- `field_aliases: dict[str, str]`
	- `field_mapping() -> dict[str, str]`
- `Importer`
	- `import_data(file, resource, allow_overwrite=False) -> ImportResult`
	- `parse(file, resource) -> TTable`
	- `validate(data, resource, allow_overwrite) -> tuple[TTable, list[TError]]`
	- `transform(data, resource) -> TTable`
	- `persist(data, resource, allow_overwrite) -> int`
- `Exporter`
	- `query(resource, params=None) -> TTable`
	- `serialize(data, fmt) -> bytes`
	- `render(data, fmt) -> ByteStream`
	- `stream(resource, fmt, filename, media_type, params=None) -> ExportPayload`
- `ImportExportService`
	- `upload_parse_validate(file, column_aliases, validate_fn, allow_overwrite=False, unique_fields=None, db_checks=None, allowed_extensions=None, allowed_mime_types=None) -> ImportValidateResponse`
	- `preview(import_id, checksum, page, page_size, kind) -> ImportPreviewResponse`
	- `commit(body, persist_fn, lock_namespace="import") -> ImportCommitResponse`

**Config and Facades**

- `resolve_config(...) -> ImportExportConfig`
- `parse_tabular_file(file_path, filename)`
- `normalize_columns(df, column_mapping)`
- `dataframe_to_preview_rows(df)`
- `collect_infile_duplicates(df, unique_fields)`
- `run_db_checks(db, df, specs, allow_overwrite=False)`

**Errors**

- `ImportExportError` with `message`, `status_code`, `details`, `error_code`
- `ParseError` / `ValidationError` / `PersistError` / `ExportError`

**ImportExportError error_code list (common)**

- `missing_dependency`: Optional backend dependency is not installed.
- `unsupported_media_type`: File extension or MIME type is not allowed.
- `import_export_error`: Default fallback code for generic errors.

## API Behavior Details

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

- Required: `import_id`, `checksum`, `page`, `page_size`, `kind`
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

## Example Snippets

**1) Define Resource and Importer**

```python
from fastapi_import_export import Importer, Resource


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

**3) Service workflow**

```python
from fastapi_import_export.service import ImportExportService


svc = ImportExportService(db=object())
resp = await svc.upload_parse_validate(
    file=file,
    column_aliases=UserResource.field_mapping(),
    validate_fn=validate_fn,
)
commit = await svc.commit(body=commit_body, persist_fn=persist_fn)
```

**4) Upload allowlist configuration**

```python
from fastapi_import_export.config import resolve_config


cfg = resolve_config(allowed_extensions=[".csv"], allowed_mime_types=["text/csv"])
svc = ImportExportService(db=object(), config=cfg)
```

## Constraints

- Does not manage database connections.
- Does not own ORM, only adapts.
- Does not handle authentication or authorization.
