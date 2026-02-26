API Reference
=============

Easy Layer (Top-level)
----------------------

.. code-block:: python

   export_csv(source, *, resource=None, params=None, options=None) -> ExportPayload
   export_xlsx(source, *, resource=None, params=None, options=None) -> ExportPayload
   import_csv(file, *, resource, validate_fn, persist_fn, options=None) -> ImportResult
   import_xlsx(file, *, resource, validate_fn, persist_fn, options=None) -> ImportResult

Options
-------

.. code-block:: python

   class ExportOptions:
       filename: str | None
       media_type: str | None
       include_bom: bool = False
       line_ending: str = "\\r\\n"
       chunk_size: int = 64 * 1024
       columns: list[str] | None

   class ImportOptions:
       db: Any | None
       allow_overwrite: bool = False
       overwrite_mode: str | None = None  # reject | upsert | replace
       unique_fields: list[str] | None
       db_checks: list[DbCheckSpec] | None
       allowed_extensions: Iterable[str] | None
       allowed_mime_types: Iterable[str] | None

Advanced Service Constructor
----------------------------

.. code-block:: python

   ImportExportService(
       db=...,
       redis_client=None,
       event_hook=None,  # optional hook: event dict -> None/awaitable
       config=None,
       base_dir=None,
       max_upload_mb=20,
       lock_ttl_seconds=300,
   )

``event_hook`` receives structured lifecycle events:

- ``upload_parse_validate.started/completed/failed``
- ``preview.started/completed/failed``
- ``commit.started/completed/failed``

Overwrite Semantics
-------------------

Stable priority order:

1. ``overwrite_mode`` (when provided)
2. ``allow_overwrite`` compatibility fallback

Allowed values:

- ``reject``
- ``upsert``
- ``replace``

Error Contract
--------------

Structured validation errors use ``ImportErrorItem``:

- ``row_number``
- ``field``
- ``type``
- ``message``

Unified error code dictionary:

- ``schema_error``
- ``type_error``
- ``db_conflict``

Resource Mapping
----------------

- ``field_aliases``: import mapping (input header -> field)
- ``export_aliases``: export mapping (field -> output header)
- ``field_codecs``: per-field codec overrides
- ``model``: ORM model for auto inference (when fields are not declared)
- ``exclude_fields``: extra fields to exclude during auto inference
- ``export_mapping()`` rule:
  - use ``export_aliases`` when present
  - else invert ``field_aliases`` if reversible
  - else identity mapping

Advanced Namespace
------------------

Advanced APIs live under ``fastapi_import_export.advanced``.

Extension Hooks
---------------

- ``Exporter.serialize``: your custom serializer (data -> bytes)
- ``Exporter.render``: your custom renderer (bytes -> AsyncIterator[bytes])
- ``Importer.parse/validate/transform/persist``: customize the import pipeline
