# fastapi-import-export

FastAPI-first import/export utilities that keep your domain model decoupled.

Other languages: [README_CN.md](README_CN.md) | [README_JP.md](README_JP.md)

## Features

- Async-first lifecycle hooks for import and export.
- Explicit Resource mapping to avoid ORM coupling.
- Pluggable backends for parsing, storage, and validation.
- Streaming export payloads for large datasets.

## Requirements

- Python 3.12-3.14
- FastAPI 0.128+

## Compatibility Matrix

| Component | Supported | Notes                                |
| --------- | --------- | ------------------------------------ |
| Python    | 3.12-3.14 | Tested with async-first workflows.   |
| FastAPI   | 0.128+    | Uses UploadFile and async endpoints. |
| Pydantic  | 2.x       | Schemas rely on BaseModel.           |
| polars    | 1.x       | Included by default.                 |
| openpyxl  | 3.x       | Included by default.                 |

## Why Not django-import-export

- Django-centric ORM/Admin coupling does not fit FastAPI async workflows.
- This library is async-first and designed as a toolkit, not a framework.
- Stable, composable APIs with explicit lifecycle hooks.

## Core Boundaries

- Do not manage DB connections.
- Do not own ORM, only adapt.
- Do not handle auth.
- Do not own storage (pluggable backends only).

## Install

Standard install (batteries included):

```bash
pip install fastapi-import-export
# or
uv add fastapi-import-export
```

Includes Polars/XLSX/storage helpers. ORM adapters are optional:

```bash
pip install fastapi-import-export[sqlalchemy]
# or
pip install fastapi-import-export[sqlmodel]
# or
pip install fastapi-import-export[tortoise]
# or
uv add fastapi-import-export[sqlalchemy]
# or
uv add fastapi-import-export[sqlmodel]
# or
uv add fastapi-import-export[tortoise]
```

Install your database driver separately if needed (e.g. `asyncpg`, `aiomysql`).

Development & unit-test deps:

```bash
pip install fastapi-import-export pytest pytest-asyncio pytest-cov anyio
# or
uv add --group dev fastapi-import-export pytest pytest-asyncio pytest-cov anyio
```

E2E integration-test deps (optional, for running example apps):

```bash
pip install fastapi-import-export[sqlalchemy] httpx python-multipart aiosqlite
# or
uv add --group e2e fastapi-import-export[sqlalchemy] httpx python-multipart aiosqlite
```

## Quick Start (Easy)

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

### 2) Import CSV/XLSX in One Call

```python
from fastapi import APIRouter, UploadFile
from fastapi_import_export import import_csv

router = APIRouter()


async def validate_fn(db, df, *, allow_overwrite: bool = False):
    return df, []


async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
    return int(valid_df.height)


@router.post("/import")
async def import_data(file: UploadFile):
    return await import_csv(
        file,
        resource=UserResource,
        validate_fn=validate_fn,
        persist_fn=persist_fn,
    )
```

### 3) Export CSV/XLSX

```python
from fastapi import StreamingResponse
from fastapi_import_export import export_csv


async def query_fn(*, resource, params=None):
    return [
        {"id": 1, "username": "alice"},
        {"id": 2, "username": "bob"},
    ]


payload = await export_csv(query_fn, resource=UserResource)
return StreamingResponse(payload.stream, media_type=payload.media_type)
```

## ORM Adapters (Optional)

Adapters live under `fastapi_import_export.contrib` for SQLAlchemy/SQLModel/Tortoise.
Install one of:

```bash
pip install fastapi-import-export[sqlalchemy]
# or
pip install fastapi-import-export[sqlmodel]
# or
pip install fastapi-import-export[tortoise]
```

What you get:

- Auto field inference from ORM models (column order and required fields).
- Auto type conversion via codecs (Enum/Date/Datetime/Decimal/Bool).
- Override per-field codecs with `field_codecs` / `__import_export_codecs__`.

## Codecs (Widget System)

Codecs handle common type conversion for import/export. Built-ins include
Enum/Date/Datetime/Decimal/Bool. You can register custom codecs per field.
Easy layer automatically applies codecs before `validate_fn/persist_fn`, and
formats values during export.

```python
from enum import Enum

from fastapi_import_export import Resource
from fastapi_import_export.codecs import DateCodec, DecimalCodec, EnumCodec


class Status(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class BookResource(Resource):
    field_codecs = {
        "status": EnumCodec(Status),
        "published_at": DateCodec(),
        "price": DecimalCodec(),
    }
```

## Resource Model Binding (Lightweight)

If a Resource declares `model` but **does not declare fields**, the library
infers fields from the ORM model:

- Source: `model.__table__.columns` (SQLAlchemy/SQLModel) or `model._meta` (Tortoise)
- Auto-exclude: primary key (`id`), `created_at`, `updated_at`, and soft-delete flags
- Configurable: `exclude_fields = ["password"]`
- Explicit wins: `field_aliases` always overrides auto mapping

```python
class BookResource(Resource):
    model = Book
    exclude_fields = ["password"]
    field_aliases = {"Author": "author"}  # overrides auto mapping
```

## Advanced (Hooks)

Advanced APIs live under `fastapi_import_export.advanced` and expose the full
hook-based lifecycle.

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
from fastapi_import_export.advanced import Importer


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)
```

### 3) FastAPI Integration

```python
from uuid import UUID

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

## Exporter Usage Example

If Excel shows garbled characters for CSV, emit UTF-8 BOM (use `utf-8-sig`).

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

## Pluggable Backend Facades

- parse/storage/validation/db_validation are lazy-loaded facades.
- Missing dependencies only occur if you remove bundled packages or use an
  optional adapter/backend/driver that is not installed (e.g. ORM adapters without
  installing the matching extra).

## Upload Allowlist Configuration

Priority order: per-call override > resolve_config parameters > environment variables > defaults.

Per-call override:

```python
await svc.upload_parse_validate(
    file=file,
    column_aliases=UserResource.field_mapping(),
    validate_fn=service_validate_fn,
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

## Unique Constraint Detection

When committing imported data, the library automatically detects unique constraint
violations from the database and returns a user-friendly error response. The
`constraint_parser` module supports precise error parsing for five databases:

| Database        | Error Pattern                                         | Extracted Info              |
| --------------- | ----------------------------------------------------- | --------------------------- |
| PostgreSQL      | `Key (col)=(val) already exists.`                     | columns, values, constraint |
| MySQL / MariaDB | `Duplicate entry 'val' for key 'key_name'`            | values, constraint          |
| SQLite          | `UNIQUE constraint failed: table.col`                 | columns                     |
| SQL Server      | `Violation of UNIQUE KEY constraint 'name'`           | values, constraint          |
| Oracle          | `ORA-00001: unique constraint (SCHEMA.NAME) violated` | constraint                  |

You can also use the parser directly in your own code:

```python
from fastapi_import_export.advanced import ConstraintDetail, parse_unique_constraint_error

detail: ConstraintDetail | None = parse_unique_constraint_error(
    str(exc), detail_text=getattr(getattr(exc, "orig", None), "detail", "")
)
if detail:
    print(detail.db_type, detail.columns, detail.values)
```

## End-to-End Example

Below is a minimal end-to-end flow that supports upload, validate, preview, and commit.

```python
from uuid import UUID

from fastapi import APIRouter, UploadFile

from fastapi_import_export.advanced import Importer, Resource
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.advanced import ImportExportService


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


async def service_validate_fn(db, df, *, allow_overwrite: bool = False):
    return df, []


async def service_persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
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
        validate_fn=service_validate_fn,
    )


@router.get("/import/preview")
async def import_preview(import_id: UUID, checksum: str, page: int = 1, page_size: int = 50):
    return await svc.preview(
        import_id=import_id,
        checksum=checksum,
        page=page,
        page_size=page_size,
        kind="all",
    )


@router.post("/import/commit")
async def import_commit(body: ImportCommitRequest):
    return await svc.commit(body=body, persist_fn=service_persist_fn)
```

## FAQ

**Why do I get missing dependency errors?**

You likely removed bundled dependencies or are using an optional adapter/driver
that is not installed (e.g. ORM adapters without the matching extra). Reinstall the base
package or add the missing adapter/driver.

**Why are my rows filtered after validation?**

The service removes rows that fail validation when generating `valid.parquet`.
Use preview with `kind=all` to inspect the original parsed data.

## Troubleshooting

- **Upload too large**: Increase `max_upload_mb` when creating `ImportExportService`.
- **checksum mismatch**: Ensure the client passes the checksum from `upload_parse_validate`.
- **missing_dependency**: Reinstall bundled dependencies or install the required adapter/driver.
- **db_conflict errors**: Check unique constraints and whether soft-deleted records exist.

## Testing

Run the unit test suite (see [Install](#install) for dependency setup):

```bash
pytest tests/ -v
```

Run the E2E integration tests:

```bash
pytest examples/ -v
```

The `examples/` directory contains complete FastAPI applications for SQLAlchemy, SQLModel, and Tortoise ORM, each covering the full HTTP lifecycle: upload, preview, commit, and export against an in-memory SQLite database.

## License

[MIT](LICENSE)
