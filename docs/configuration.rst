Configuration
=============

Defaults (Easy Layer)
---------------------

- CSV default: no BOM (``include_bom=False``), line ending ``\\r\\n``.
- Media type inferred from format.
- Column order:
  ``options.columns`` > ``Resource`` field order > inferred from rows.
- Export mapping:
  ``export_aliases`` > invertible ``field_aliases`` > identity.

Upload Allowlist
----------------

You can control allowed extensions and MIME types via:

- ``ImportOptions.allowed_extensions`` / ``ImportOptions.allowed_mime_types``
- or per-call parameters in the advanced service
- or environment-based config (advanced)
