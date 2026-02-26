Getting Started
===============

Easy Layer (5-minute success)
-----------------------------

Define a Resource:

.. code-block:: python

   from fastapi_import_export import Resource


   class UserResource(Resource):
       id: int | None
       username: str
       email: str

       field_aliases = {
           "Username": "username",
           "Email": "email",
       }

Import CSV/XLSX:

.. code-block:: python

   from fastapi import UploadFile
   from fastapi_import_export import import_csv
    from fastapi_import_export.options import ImportOptions

   async def validate_fn(db, df, *, allow_overwrite: bool = False):
       return df, []

   async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
       return int(valid_df.height)

   async def import_data(file: UploadFile):
       return await import_csv(
           file,
           resource=UserResource,
           validate_fn=validate_fn,
           persist_fn=persist_fn,
           options=ImportOptions(overwrite_mode="upsert"),
       )

Overwrite behavior:

- ``overwrite_mode`` has higher priority when provided.
- ``allow_overwrite`` remains backward compatible.
- Recommended values: ``reject`` / ``upsert`` / ``replace``.

Export CSV/XLSX:

.. code-block:: python

   from fastapi import StreamingResponse
   from fastapi_import_export import export_csv

   async def query_fn(*, resource, params=None):
       return [{"id": 1, "username": "alice"}]

   payload = await export_csv(query_fn, resource=UserResource)
   return StreamingResponse(payload.stream, media_type=payload.media_type)

Codecs (Widget System)
----------------------

Codecs handle common type conversion for import/export. Built-ins include
Enum/Date/Datetime/Decimal/Bool, and you can register them per field.
The easy layer applies codecs before ``validate_fn/persist_fn`` and formats
values during export.

.. code-block:: python

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

Error Payload Shape
-------------------

Validation errors are structured and front-end friendly:

- ``row_number``: source row number
- ``field``: field/column name
- ``type``: normalized code (``schema_error`` / ``type_error`` / ``db_conflict``)
- ``message``: human-readable description

Resource Model Binding
----------------------

When a Resource defines ``model`` but **does not declare fields**, the library
infers fields from the ORM model. Explicit ``field_aliases`` always override
the auto mapping.

.. code-block:: python

   class BookResource(Resource):
       model = Book
       exclude_fields = ["password"]
       field_aliases = {"Author": "author"}

Advanced Layer
--------------

The full hook-based lifecycle is available under
``fastapi_import_export.advanced``.
