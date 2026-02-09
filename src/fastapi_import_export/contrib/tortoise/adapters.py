"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: adapters.py
@DateTime: 2026-02-09
@Docs: Tortoise ORM adapter helpers.
Tortoise ORM 适配器辅助函数。
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi_import_export.codecs import BoolCodec, Codec, DateCodec, DatetimeCodec, DecimalCodec, EnumCodec
from fastapi_import_export.exceptions import ImportExportError


def _require_tortoise() -> Any:
    try:
        import tortoise

        return tortoise
    except Exception as exc:  # pragma: no cover
        raise ImportExportError(
            message="Missing optional dependency: tortoise-orm / 缺少可选依赖: tortoise-orm",
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
    generated: bool
    has_default: bool
    python_type: type[Any] | None
    field: Any


def get_field_specs(model: Any) -> list[FieldSpec]:
    _require_tortoise()
    meta = getattr(model, "_meta", None)
    if meta is None:
        raise ImportExportError(message="Tortoise model missing _meta / 模型缺少 _meta")
    fields_map = getattr(meta, "fields_map", None)
    if not isinstance(fields_map, dict):
        raise ImportExportError(message="Tortoise model fields_map missing / 缺少 fields_map")
    projection = getattr(meta, "fields_db_projection", None)
    if isinstance(projection, dict) and projection:
        field_names = list(projection.keys())
    else:
        field_names = list(fields_map.keys())

    specs: list[FieldSpec] = []
    for name in field_names:
        field = fields_map.get(name)
        if field is None:
            continue
        python_type = getattr(field, "python_type", None)
        specs.append(
            FieldSpec(
                name=str(name),
                nullable=bool(getattr(field, "null", False)),
                primary_key=bool(getattr(field, "pk", False) or getattr(field, "primary_key", False)),
                generated=bool(getattr(field, "generated", False)),
                has_default=getattr(field, "default", None) is not None,
                python_type=python_type if isinstance(python_type, type) else None,
                field=field,
            )
        )
    return specs


def resolve_import_specs(specs: list[FieldSpec], columns: list[str] | None) -> list[FieldSpec]:
    if columns is not None:
        spec_map = {spec.name: spec for spec in specs}
        return [spec_map[name] for name in columns if name in spec_map]
    return [spec for spec in specs if not (spec.primary_key and spec.generated)]


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

    resolved: dict[str, Codec] = {}
    for spec in specs:
        if spec.name in custom:
            resolved[spec.name] = custom[spec.name]
            continue
        codec = _infer_codec(spec)
        if codec is not None:
            resolved[spec.name] = codec
    return resolved


def _infer_codec(spec: FieldSpec) -> Codec | None:
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

    enum_type = getattr(spec.field, "enum_type", None)
    if enum_type is not None:
        return EnumCodec(enum_type)
    return None


def cast_basic(value: Any, python_type: type[Any] | None) -> Any:
    if python_type is None:
        return value
    if python_type is int:
        return int(str(value).strip())
    if python_type is float:
        return float(str(value).strip())
    return value
