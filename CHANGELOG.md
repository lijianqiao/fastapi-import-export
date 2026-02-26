# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Changed

- Added standard CI workflow for push/PR gates (lint, unit tests, e2e tests, package build).
- Promoted project maturity classifier from Alpha to Beta.
- Unified `sqlmodel` lower bound to `>=0.0.32` across extras/groups.
- Added production cleanup guidance for temporary import artifacts.
- Added explicit changelog and compatibility policy references.

## [0.2.0] - 2026-02-08

### Added

- Easy-layer APIs: `import_csv`, `import_xlsx`, `export_csv`, `export_xlsx`.
- Advanced lifecycle APIs with `Importer`, `Exporter`, and `ImportExportService`.
- Pluggable facades for parse/storage/validation/db validation.
- ORM adapter support for SQLAlchemy, SQLModel, and Tortoise (optional extras).
- Unique constraint parsing across PostgreSQL/MySQL/SQLite/SQL Server/Oracle.

## Compatibility Policy

- Public APIs documented in README and docs are kept backward compatible within minor versions whenever possible.
- Breaking changes are released in major versions and documented in advance in release notes.
- Python and FastAPI support windows are reflected in `pyproject.toml` classifiers and README compatibility matrix.