"""Import/Export Errors
导入导出异常

Errors that occur during the import/export process, including error messages, status codes, and detailed information.
导入导出过程中发生的异常，包含错误消息、状态码和详细信息。
"""

from typing import Any


class ImportExportError(Exception):
    """Import/Export Errors
    导入导出异常

    Errors that occur during the import/export process, including error messages, status codes, and detailed information.
    导入导出过程中发生的异常，包含错误消息、状态码和详细信息。

    Attributes:
        message (str): 异常的错误消息。
        status_code (int): 异常对应的 HTTP 状态码，默认值为 400。
        details (Any | None): 异常的详细信息，可选。
    """

    def __init__(self, *, message: str, status_code: int = 400, details: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details
