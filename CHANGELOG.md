# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Added explicit overwrite strategy support (`overwrite_mode`: `reject`/`upsert`/`replace`) across easy layer, service flow, and contrib adapters.
- Added unified validation error code dictionary and normalization helpers: `schema_error`, `type_error`, `db_conflict`.
- Added built-in book template contract presets (`get_book_template_contract`, `BOOK_TEMPLATE_COLUMNS`, `BOOK_STATUS_ENUM`) and fixture example.
- Added optional service observability hook (`event_hook`) with lifecycle events for validate/preview/commit.
- Added benchmark scaffold under `benchmarks/benchmark_import_service.py` with:
	- multi-round stats (`median`/`p95`),
	- warmup rounds (`--warmup`),
	- deterministic generation (`--seed`),
	- result export (`--export-json`),
	- baseline comparison (`--baseline-json`) and regression gate (`--fail-on-regression`, `--regression-threshold`).
- Added dedicated GitHub Actions performance gate workflow (`.github/workflows/performance-gate.yml`) based on `.perf/baseline.json`.

### Changed

- Standardized import validation error payload shape to include `type` in `ImportErrorItem`.
- Front-loaded type coercion/validation recommendations into validate stage to reduce commit-time failures.
- Expanded docs set with contracts, observability, and performance guidance, including CI gate usage and baseline policy.

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