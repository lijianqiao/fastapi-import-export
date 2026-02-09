"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: formats.py
@DateTime: 2026-02-09
@Docs: Export/import format constants and helpers.
导入导出格式常量与辅助函数。
"""

from enum import StrEnum


class ExportFormat(StrEnum):
    """Supported export formats.
    支持的导出格式。
    """

    CSV = "csv"
    XLSX = "xlsx"


CSV_ALLOWED_EXTENSIONS: tuple[str, ...] = (".csv",)
XLSX_ALLOWED_EXTENSIONS: tuple[str, ...] = (".xlsx", ".xlsm", ".xls")

CSV_ALLOWED_MIME_TYPES: tuple[str, ...] = (
    "text/csv",
    "application/csv",
    "text/plain",
)
XLSX_ALLOWED_MIME_TYPES: tuple[str, ...] = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
)

_MEDIA_TYPES: dict[ExportFormat, str] = {
    ExportFormat.CSV: "text/csv; charset=utf-8",
    ExportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_EXTENSIONS: dict[ExportFormat, str] = {
    ExportFormat.CSV: ".csv",
    ExportFormat.XLSX: ".xlsx",
}


def media_type_for(fmt: ExportFormat | str) -> str:
    """Return default media type for a format.
    返回格式的默认 media type。

    Args:
        fmt: Export format.
            导出格式。
    Returns:
        str: Default media type for the format.
            格式的默认 media type。

    """
    key = ExportFormat(fmt)
    return _MEDIA_TYPES[key]


def extension_for(fmt: ExportFormat | str) -> str:
    """Return default file extension for a format.
    返回格式的默认文件扩展名。

    Args:
        fmt: Export format.
            导出格式。
    Returns:
        str: Default file extension for the format.
            格式的默认文件扩展名。

    """
    key = ExportFormat(fmt)
    return _EXTENSIONS[key]
