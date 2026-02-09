"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: adapters.py
@DateTime: 2026-02-09
@Docs: SQLAlchemy adapter helpers.
SQLAlchemy 适配器辅助函数。
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi_import_export.codecs import BoolCodec, Codec, DateCodec, DatetimeCodec, DecimalCodec, EnumCodec
from fastapi_import_export.exceptions import ImportExportError


def _require_sqlalchemy() -> Any:
    try:
        import sqlalchemy as sa

        return sa
    except Exception as exc:  # pragma: no cover
        raise ImportExportError(
            message="Missing optional dependency: sqlalchemy / 缺少可选依赖: sqlalchemy",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


def _require_polars() -> Any:
    try:
        import polars as pl

        return pl
    except Exception as exc:  # pragma: no cover
        raise ImportExportError(
            message="Missing optional dependency: polars / 缺少可选依赖: polars",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    nullable: bool
    primary_key: bool
    has_default: bool
    autoincrement: bool
    type_: Any
    python_type: type[Any] | None


def get_field_specs(model: Any) -> list[FieldSpec]:
    table = getattr(model, "__table__", None)
    if table is None:
        raise ImportExportError(message="SQLAlchemy model missing __table__ / 模型缺少 __table__")
    specs: list[FieldSpec] = []
    for col in list(table.columns):
        python_type: type[Any] | None = None
        try:
            python_type = col.type.python_type
        except Exception:
            python_type = None
        autoincrement = getattr(col, "autoincrement", False)
        specs.append(
            FieldSpec(
                name=str(col.name),
                nullable=bool(getattr(col, "nullable", True)),
                primary_key=bool(getattr(col, "primary_key", False)),
                has_default=bool(getattr(col, "default", None) is not None or getattr(col, "server_default", None)),
                autoincrement=bool(autoincrement) if autoincrement is not None else False,
                type_=col.type,
                python_type=python_type,
            )
        )
    return specs


def _is_auto_pk(spec: FieldSpec) -> bool:
    if not spec.primary_key:
        return False
    if spec.autoincrement:
        return True
    return spec.has_default


def resolve_import_specs(specs: list[FieldSpec], columns: list[str] | None) -> list[FieldSpec]:
    if columns is not None:
        spec_map = {spec.name: spec for spec in specs}
        return [spec_map[name] for name in columns if name in spec_map]
    return [spec for spec in specs if not _is_auto_pk(spec)]


def resolve_export_specs(specs: list[FieldSpec], columns: list[str] | None) -> list[FieldSpec]:
    if columns is not None:
        spec_map = {spec.name: spec for spec in specs}
        return [spec_map[name] for name in columns if name in spec_map]
    return list(specs)


def resolve_field_codecs(model: Any, specs: list[FieldSpec]) -> dict[str, Codec]:
    custom: dict[str, Codec] = {}
    for attr in ("field_codecs", "__import_export_codecs__"):
        value = getattr(model, attr, None)
        if isinstance(value, dict):
            custom.update(value)
    sa = _require_sqlalchemy()
    resolved: dict[str, Codec] = {}
    for spec in specs:
        if spec.name in custom:
            resolved[spec.name] = custom[spec.name]
            continue
        codec = _infer_codec(sa, spec)
        if codec is not None:
            resolved[spec.name] = codec
    return resolved


def _infer_codec(sa: Any, spec: FieldSpec) -> Codec | None:
    py = spec.python_type
    if py is not None and isinstance(py, type):
        if issubclass(py, Enum):
            return EnumCodec(py)
        if py is bool:
            return BoolCodec()
        if py is date:
            return DateCodec()
        if py is datetime:
            return DatetimeCodec()
        if py is Decimal:
            return DecimalCodec()
    # Fallback to SQLAlchemy types
    if isinstance(spec.type_, sa.Enum):
        enum_cls = getattr(spec.type_, "enum_class", None)
        if enum_cls is not None:
            return EnumCodec(enum_cls)
        enums = getattr(spec.type_, "enums", None)
        if enums:
            return EnumCodec(enums)
    if isinstance(spec.type_, sa.Boolean):
        return BoolCodec()
    if isinstance(spec.type_, sa.Date):
        return DateCodec()
    if isinstance(spec.type_, sa.DateTime):
        return DatetimeCodec()
    if isinstance(spec.type_, sa.Numeric):
        return DecimalCodec()
    return None


def cast_basic(value: Any, python_type: type[Any] | None) -> Any:
    if python_type is None:
        return value
    if python_type is int:
        return int(str(value).strip())
    if python_type is float:
        return float(str(value).strip())
    return value
