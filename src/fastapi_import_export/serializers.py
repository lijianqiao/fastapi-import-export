"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: serializers.py
@DateTime: 2026-02-09
@Docs: Built-in serializers for easy-layer export.
易用层内置序列化器。
"""

import csv
import io
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.options import ExportOptions


class Serializer(Protocol):
    """Serializer protocol.
    序列化器协议。
    """

    def serialize(self, *, data: Iterable[Mapping[str, Any]], options: ExportOptions) -> bytes: ...


def _infer_columns(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Infer the column order from iterable mapping rows.
    从映射行的可迭代对象中推断列顺序。

    Iterates rows in order and collects the first occurrence of each key to
    preserve header ordering for CSV/XLSX output.
    遍历行并收集每个键的首次出现位置，以便在 CSV/XLSX 输出中保持表头顺序。

    Args:
        rows: Iterable of mapping rows.
            映射行的可迭代对象。

    Returns:
        list[str]: Inferred column name list.
            推断的列名列表。
    """
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                columns.append(k)
    return columns


class CsvSerializer:
    """CSV serializer using stdlib csv.DictWriter.
    使用标准库 csv.DictWriter 的 CSV 序列化器。
    """

    def serialize(self, *, data: Iterable[Mapping[str, Any]], options: ExportOptions) -> bytes:
        """Serialize data to CSV format.
        将数据序列化为 CSV 格式。

        Args:
            data: Iterable of mapping rows.
                映射行的可迭代对象。
            options: Export options.
                导出选项。

        Returns:
            bytes: Serialized CSV data.
                序列化的 CSV 数据。
        """
        rows = list(data)
        fieldnames = options.columns or _infer_columns(rows)
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=fieldnames,
            extrasaction="ignore",
            restval="",
            lineterminator=options.line_ending,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
        encoding = "utf-8-sig" if options.include_bom else "utf-8"
        return buf.getvalue().encode(encoding)


class XlsxSerializer:
    """XLSX serializer using openpyxl.
    使用 openpyxl 的 XLSX 序列化器。
    """

    def serialize(self, *, data: Iterable[Mapping[str, Any]], options: ExportOptions) -> bytes:
        """Serialize data to XLSX format.
        将数据序列化为 XLSX 格式。

        Args:
            data: Iterable of mapping rows.
                映射行的可迭代对象。
            options: Export options.
                导出选项。

        Returns:
            bytes: Serialized XLSX data.
                序列化的 XLSX 数据。
        """
        rows = list(data)
        headers = options.columns or _infer_columns(rows)
        Workbook = _require_openpyxl()
        wb = Workbook()
        ws = wb.active
        if ws is None:
            raise RuntimeError("Workbook.active is None / Workbook.active 为空")
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h, "") for h in headers])
        ws.freeze_panes = "A2"
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()


def _require_openpyxl() -> Any:
    """Ensure openpyxl is available and return the Workbook class.
    确保 openpyxl 可用并返回 Workbook 类。

    Raises:
        ImportExportError: If openpyxl cannot be imported.
            无法导入 openpyxl 时抛出 ImportExportError。
    """
    try:
        from openpyxl import Workbook

        return Workbook
    except Exception as exc:  # pragma: no cover
        raise ImportExportError(
            message="Missing optional dependency: openpyxl / 缺少可选依赖 openpyxl",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc
