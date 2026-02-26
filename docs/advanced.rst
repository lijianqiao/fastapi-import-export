Advanced
========

The advanced hook-based API is available under:

``fastapi_import_export.advanced``

This layer exposes:

- ``Importer``: parse -> validate -> transform -> persist
- ``Exporter``: query -> serialize -> render
- ``ImportExportService``: upload/preview/commit workflow

Use this layer when you need custom pipelines, non-standard data sources, or
specialized persistence logic.

Custom Serializer / Renderer
----------------------------

- **Serializer**: implement a function that converts table-like data into
  ``bytes``. This is the core hook for CSV/XLSX/JSON or custom binary formats.
- **Renderer**: implement a function that converts ``bytes`` into an
  ``AsyncIterator[bytes]``. This is how you enable streaming or chunking.

Lifecycle Extension Rules
-------------------------

Import lifecycle (advanced):

- ``parse -> validate -> transform -> persist``
- ``validate`` returns ``(valid_data, errors)``.
- When ``errors`` is non-empty, transform/persist are skipped.
- ``allow_overwrite`` is passed through to validation and persistence hooks.

Export lifecycle (advanced):

- ``query -> serialize -> render``
- ``query`` returns table-like data.
- ``serialize`` returns ``bytes``.
- ``render`` returns ``AsyncIterator[bytes]``.

Codecs (Widget System)
----------------------

Codecs provide per-field parse/format for common types. Built-ins include
Enum/Date/Datetime/Decimal/Bool, and ORM adapters will auto-select them when
possible. You can override per field via ``field_codecs``.
The easy layer applies codecs before ``validate_fn/persist_fn`` and formats
values during export.

.. code-block:: python

   class BookResource(Resource):
       field_codecs = {"status": EnumCodec(Status)}

Resource Model Binding
----------------------

If a Resource declares ``model`` but no fields, the library infers fields from
the ORM model, excluding primary keys, timestamps, and soft-delete flags. You
can add ``exclude_fields`` or override with ``field_aliases``.

.. code-block:: python

   class BookResource(Resource):
       model = Book
       exclude_fields = ["password"]
       field_aliases = {"Author": "author"}

Pluggable Backends (Facades)
----------------------------

- ``parse`` and ``validation`` default to Polars backends (bundled by default).
- ``storage`` defaults to filesystem backend (bundled by default).
- ``ImportExportError(error_code="missing_dependency")`` occurs only if bundled
  packages are removed or a required external backend/driver is missing.

ORM Adapters (Contrib)
----------------------

The optional ORM adapters live under ``fastapi_import_export.contrib`` and
require the matching extra when you want SQLAlchemy/SQLModel/Tortoise support:

.. code-block:: bash

   pip install fastapi-import-export[sqlalchemy]
   # or
   pip install fastapi-import-export[sqlmodel]
   # or
   pip install fastapi-import-export[tortoise]
