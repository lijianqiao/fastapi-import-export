Contracts
=========

This page defines stable lifecycle contracts for the import workflow.

Lifecycle
---------

The service lifecycle is fixed as:

- ``upload_parse_validate``
- ``preview``
- ``commit``

Validate Contract
-----------------

Input:

- ``file``: upload payload (CSV/XLSX)
- ``column_aliases``: header normalization map
- ``validate_fn``: domain validation handler
- optional: ``overwrite_mode``, ``unique_fields``, ``db_checks``

Output: ``ImportValidateResponse``

- ``import_id``
- ``checksum``
- ``total_rows`` / ``valid_rows`` / ``error_rows``
- ``errors``: list of structured ``ImportErrorItem``

Preview Contract
----------------

Input:

- ``import_id``
- ``checksum``
- ``page`` / ``page_size``
- ``kind``: ``all`` or ``valid``

Output: ``ImportPreviewResponse``

- pagination fields
- row list with ``row_number`` + ``data``

Commit Contract
---------------

Input:

- ``ImportCommitRequest``
- ``persist_fn``

Output: ``ImportCommitResponse``

- ``status``
- ``imported_rows``
- ``created_at``

Behavior notes:

- Commit is idempotent for already committed imports.
- Commit is blocked when ``errors.json`` contains validation errors.
- Checksum mismatch is rejected before persistence.

Overwrite Priority
------------------

Priority is stable and documented:

1. ``overwrite_mode`` (when provided)
2. ``allow_overwrite`` fallback compatibility

Error Shape
-----------

Structured validation errors are represented as:

- ``row_number``
- ``field``
- ``type``
- ``message``

Error codes are normalized to:

- ``schema_error``
- ``type_error``
- ``db_conflict``

Observability Contract
----------------------

When ``event_hook`` is configured in ``ImportExportService``,
the service emits structured lifecycle events:

- ``upload_parse_validate.started/completed/failed``
- ``preview.started/completed/failed``
- ``commit.started/completed/failed``

Hook failures are swallowed and do not affect business flow.
