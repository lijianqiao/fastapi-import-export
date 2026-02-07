# fastapi-import-export

FastAPI-first import/export utilities that keep your domain model decoupled.

## Why not django-import-export

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
from fastapi_import_export import Importer


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

## ORM Adapter Example

```python
async def query_fn(*, resource, params=None):
    return data
```
