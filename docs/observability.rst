Observability
=============

This page describes optional service observability hooks.

Overview
--------

``ImportExportService`` supports an optional ``event_hook`` callback.
The callback receives structured lifecycle events and can be sync or async.

Design Goal
-----------

- No API break for existing users
- Optional integration for logging/metrics/tracing
- Hook failures do not break business flow

Event Payload
-------------

Each event includes:

- ``name``: event name
- ``ts``: unix timestamp (seconds)
- extra stage-specific fields

Lifecycle Events
----------------

Validate stage:

- ``upload_parse_validate.started``
- ``upload_parse_validate.completed``
- ``upload_parse_validate.failed``

Preview stage:

- ``preview.started``
- ``preview.completed``
- ``preview.failed``

Commit stage:

- ``commit.started``
- ``commit.completed``
- ``commit.failed``

Recommended Fields
------------------

For diagnostics, consumers should persist at least:

- ``import_id``
- ``checksum`` (when available)
- ``overwrite_mode`` (when available)
- ``total_rows`` / ``valid_rows`` / ``error_rows``
- ``error`` (on failed events)

Stage-specific hints:

- Validate completed: track ``total_rows``, ``valid_rows``, ``error_rows``.
- Preview completed: track ``page``, ``page_size``, ``rows_count``.
- Commit completed: track ``imported_rows``, ``idempotent``.

CI/ops troubleshooting:

- Correlate performance gate runs with ``import_id`` and stage latencies.
- Persist failed-event payloads to simplify regression triage.

Example
-------

.. code-block:: python

   from fastapi_import_export.service import ImportExportService


   events: list[dict] = []


   async def event_hook(event: dict) -> None:
       events.append(event)


   svc = ImportExportService(db=db, event_hook=event_hook)
