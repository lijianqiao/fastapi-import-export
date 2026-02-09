"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-02-09
@Docs: Advanced API namespace (formerly top-level exports).
高级 API 命名空间（原顶层导出）。
"""

from fastapi_import_export.config import ImportExportConfig, resolve_config
from fastapi_import_export.constraint_parser import ConstraintDetail, parse_unique_constraint_error
from fastapi_import_export.db_validation import DbCheckFn, DbCheckSpec, run_db_checks
from fastapi_import_export.exceptions import ExportError, ImportExportError, ParseError, PersistError, ValidationError
from fastapi_import_export.exporter import Exporter, ExportPayload
from fastapi_import_export.importer import Importer, ImportResult, ImportStatus
from fastapi_import_export.parse import ParsedTable, dataframe_to_preview_rows, normalize_columns, parse_tabular_file
from fastapi_import_export.resource import Resource
from fastapi_import_export.schemas import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportErrorItem,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportValidateResponse,
)
from fastapi_import_export.service import ImportExportService
from fastapi_import_export.service_types import (
    BuildTemplateFn,
    ExportDfFn,
    ExportResult,
    RedisLike,
    ServicePersistFn,
    ServiceValidateFn,
)
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
    "BuildTemplateFn",
    "ConstraintDetail",
    "DbCheckFn",
    "DbCheckSpec",
    "ErrorCollector",
    "ExportDfFn",
    "ExportError",
    "ExportPayload",
    "ExportResult",
    "Exporter",
    "ImportCommitRequest",
    "ImportCommitResponse",
    "ImportErrorItem",
    "ImportExportConfig",
    "ImportExportError",
    "ImportExportService",
    "ImportPaths",
    "ImportPreviewResponse",
    "ImportPreviewRow",
    "ImportResult",
    "ImportStatus",
    "ImportValidateResponse",
    "Importer",
    "ParseError",
    "ParsedTable",
    "PersistError",
    "RedisLike",
    "Resource",
    "RowContext",
    "ServicePersistFn",
    "ServiceValidateFn",
    "ValidationError",
    "cleanup_expired_imports",
    "create_export_path",
    "dataframe_to_preview_rows",
    "delete_export_file",
    "get_import_paths",
    "new_import_id",
    "normalize_columns",
    "now_ts",
    "parse_tabular_file",
    "parse_unique_constraint_error",
    "read_meta",
    "resolve_config",
    "run_db_checks",
    "sha256_file",
    "write_meta",
]
