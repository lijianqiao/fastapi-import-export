"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: options.py
@DateTime: 2026-02-09
@Docs: Explicit configuration options for easy-layer APIs.
明确配置选项，供易用层 API 使用。
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi_import_export.db_validation import DbCheckSpec


@dataclass(frozen=True, slots=True)
class ExportOptions:
    """Export options (explicit configuration layer).
    导出选项（显式配置层）。
    """

    filename: str | None = None
    media_type: str | None = None
    include_bom: bool = False
    line_ending: str = "\r\n"
    chunk_size: int = 64 * 1024
    columns: list[str] | None = None


@dataclass(frozen=True, slots=True)
class ImportOptions:
    """Import options (explicit configuration layer).
    导入选项（显式配置层）。
    """

    db: Any | None = None
    allow_overwrite: bool = False
    unique_fields: list[str] | None = None
    db_checks: list[DbCheckSpec] | None = None
    allowed_extensions: Iterable[str] | None = None
    allowed_mime_types: Iterable[str] | None = None
