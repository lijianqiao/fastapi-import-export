"""fastapi_import_export package.

FastAPI Import/Export utilities intended for reuse across projects.

本包提供可复用的 FastAPI 导入导出基础设施，目标是在不同项目中直接复用。

Examples:
    >>> from fastapi_import_export import ImportExportService
    >>> svc = ImportExportService(db=object())
"""

from fastapi_import_export.config import ImportExportConfig, resolve_config
from fastapi_import_export.db_validation import DbCheckFn, DbCheckSpec, run_db_checks
from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.parse import ParsedTable, dataframe_to_preview_rows, normalize_columns, parse_tabular_file
from fastapi_import_export.schemas import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportErrorItem,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportValidateResponse,
)
from fastapi_import_export.service import ExportResult, ImportExportService
from fastapi_import_export.storage import (
    ImportPaths,
    cleanup_expired_imports,
    create_export_path,
    delete_export_file,
    get_import_paths,
    new_import_id,
    now_ts,
    read_meta,
    sha256_file,
    write_meta,
)
from fastapi_import_export.validation_core import ErrorCollector, RowContext

__all__ = [
    "ImportExportError",
    "DbCheckFn",
    "DbCheckSpec",
    "run_db_checks",
    "ErrorCollector",
    "RowContext",
    "ImportExportConfig",
    "resolve_config",
    "ParsedTable",
    "parse_tabular_file",
    "normalize_columns",
    "dataframe_to_preview_rows",
    "ImportCommitRequest",
    "ImportCommitResponse",
    "ImportErrorItem",
    "ImportPreviewResponse",
    "ImportPreviewRow",
    "ImportValidateResponse",
    "ExportResult",
    "ImportExportService",
    "ImportPaths",
    "cleanup_expired_imports",
    "create_export_path",
    "delete_export_file",
    "get_import_paths",
    "new_import_id",
    "now_ts",
    "read_meta",
    "sha256_file",
    "write_meta",
]
