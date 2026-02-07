"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: exceptions.py
@DateTime: 2026-02-08
@Docs: Import/export error hierarchy.
导入导出异常体系。
"""

from typing import Any


class ImportExportError(Exception):
    """
    Import/Export Errors.
    导入导出异常。

    Errors that occur during the import/export process.
    导入导出过程中发生的异常。

    Attributes:
        message: Error message.
        message: 错误消息。
        status_code: HTTP status code.
        status_code: HTTP 状态码。
        details: Error details.
        details: 错误详情。
        error_code: Stable error code.
        error_code: 稳定错误码。
    """

    def __init__(
        self,
        *,
        message: str,
        status_code: int = 400,
        details: Any | None = None,
        error_code: str = "import_export_error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details
        self.error_code = error_code


class ParseError(ImportExportError):
    """
    Parse error.
    解析错误。
    """


class ValidationError(ImportExportError):
    """
    Validation error.
    校验错误。
    """


class PersistError(ImportExportError):
    """
    Persist error.
    持久化错误。
    """


class ExportError(ImportExportError):
    """
    Export error.
    导出错误。
    """
