# fastapi-import-export

FastAPI-first import/export utilities that keep your domain model decoupled.

Other languages: [README_CN.md](README_CN.md) | [README_JP.md](README_JP.md)

## Features

- Async-first lifecycle hooks for import and export.
- Explicit Resource mapping to avoid ORM coupling.
- Optional backends for parsing, storage, and validation.
- Streaming export payloads for large datasets.

## Requirements

- Python 3.12-3.14
- FastAPI 0.128+

## Compatibility Matrix

| Component  | Supported | Notes                                     |
| ---------- | --------- | ----------------------------------------- |
| Python     | 3.12-3.14 | Tested with async-first workflows.        |
| FastAPI    | 0.128+    | Uses UploadFile and async endpoints.      |
| Pydantic   | 2.x       | Schemas rely on BaseModel.                |
| polars     | 1.x       | Optional parsing/validation backend.      |
| openpyxl   | 3.x       | Excel parsing backend.                    |

## Why Not django-import-export

- Django-centric ORM/Admin coupling does not fit FastAPI async workflows.
- This library is async-first and designed as a toolkit, not a framework.
- Stable, composable APIs with explicit lifecycle hooks.

## Core Boundaries

- Do not manage DB connections.
- Do not own ORM, only adapt.
- Do not handle auth.
- Do not own storage (optional backends only).

## Install

Minimal (core only):

```bash
pip install fastapi-import-export
```

Common optional deps:

```bash
pip install fastapi-import-export[polars,xlsx,storage]
```

All optional deps:

```bash
pip install fastapi-import-export[full]
```

## Extras

- polars: DataFrame parsing and validation backends.
- xlsx: Excel parsing support (openpyxl).
- storage: Filesystem storage backend helpers.
- full: All optional dependencies.

## Quick Start

### 1) Define a Resource

```python
from fastapi_import_export import Resource


class UserResource(Resource):
    id: int | None
    username: str
    email: str

    field_aliases = {
        "Username": "username",
        "Email": "email",
    }
```

### 2) Build an Importer

```python
from fastapi_import_export import Importer


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)
```

### 3) FastAPI Integration

```python
from fastapi import APIRouter, UploadFile


router = APIRouter()


@router.post("/import")
async def import_data(file: UploadFile):
    result = await importer.import_data(file=file, resource=UserResource)
    return result
```

## Async Import Example

```python
async def validate_fn(*, data, resource, allow_overwrite=False):
    return data, []


async def persist_fn(*, data, resource, allow_overwrite=False):
    return 100
```

## Large Export (Streaming)

```python
from fastapi import StreamingResponse


payload = await exporter.stream(
    resource=UserResource,
    fmt="csv",
    filename="users.csv",
    media_type="text/csv",
)
return StreamingResponse(payload.stream, media_type=payload.media_type)
```

## Optional Backend Facades

- parse/storage/validation/db_validation are lazy-loaded facades.
- Missing extras raise ImportExportError with a clear install hint.

## Upload Allowlist Configuration

Priority order: per-call override > resolve_config parameters > environment variables > defaults.

Per-call override:

```python
await svc.upload_parse_validate(
    file=file,
    column_aliases=UserResource.field_mapping(),
    validate_fn=validate_fn,
    allowed_extensions=[".csv"],
    allowed_mime_types=["text/csv"],
)
```

Config-level override:

```python
from fastapi_import_export.config import resolve_config


cfg = resolve_config(
    allowed_extensions=[".csv", ".xlsx"],
    allowed_mime_types=["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
)
svc = ImportExportService(db=object(), config=cfg)
```

Environment variable example:

```bash
export IMPORT_EXPORT_ALLOWED_EXTENSIONS=".csv,.xlsx"
export IMPORT_EXPORT_ALLOWED_MIME_TYPES="text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

## End-to-End Example

Below is a minimal end-to-end flow that supports upload, validate, preview, and commit.

```python
from fastapi import APIRouter, UploadFile

from fastapi_import_export import Importer, Resource
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import ImportExportService


class UserResource(Resource):
    id: int | None
    username: str
    email: str

    field_aliases = {
        "Username": "username",
        "Email": "email",
    }


async def parse_fn(*, file: UploadFile, resource: type[Resource]):
    return await some_parse_impl(file=file, resource=resource)


async def validate_fn(*, data, resource: type[Resource], allow_overwrite: bool = False):
    return data, []


async def transform_fn(*, data, resource: type[Resource]):
    return data


async def persist_fn(*, data, resource: type[Resource], allow_overwrite: bool = False) -> int:
    return 100


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)

router = APIRouter()


@router.post("/import")
async def import_data(file: UploadFile):
    return await importer.import_data(file=file, resource=UserResource)


# Optional: use the service class for upload/preview/commit workflow
svc = ImportExportService(db=object())


@router.post("/import/validate")
async def import_validate(file: UploadFile):
    return await svc.upload_parse_validate(
        file=file,
        column_aliases=UserResource.field_mapping(),
        validate_fn=validate_fn,
    )


@router.get("/import/preview")
async def import_preview(import_id: str, checksum: str, page: int = 1, page_size: int = 50):
    return await svc.preview(
        import_id=import_id,
        checksum=checksum,
        page=page,
        page_size=page_size,
        kind="all",
    )


@router.post("/import/commit")
async def import_commit(body: ImportCommitRequest):
    return await svc.commit(body=body, persist_fn=persist_fn)
```

## FAQ

**Why do I get missing dependency errors?**

Install the matching extras, for example:

```bash
pip install fastapi-import-export[polars,xlsx,storage]
```

**Why is ImportExportService not exported from the package root?**

Import it from the service module:

```python
from fastapi_import_export.service import ImportExportService
```

**Why are my rows filtered after validation?**

The service removes rows that fail validation when generating `valid.parquet`.
Use preview with `kind=all` to inspect the original parsed data.

## Troubleshooting

- **Upload too large**: Increase `max_upload_mb` when creating `ImportExportService`.
- **checksum mismatch**: Ensure the client passes the checksum from `upload_parse_validate`.
- **missing_dependency**: Install the correct extras for parse/storage/validation backends.
- **db_conflict errors**: Check unique constraints and whether soft-deleted records exist.

## Migration Notes

- ImportExportService and ExportResult are not exported from the package root.
  Import from fastapi_import_export.service if you still use them.

## License

[MIT](LICENSE)
