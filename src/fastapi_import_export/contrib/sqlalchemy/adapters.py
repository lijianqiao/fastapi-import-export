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
    """
    Ensure SQLAlchemy is available.
    确保 SQLAlchemy 可用。

    Raises:
        ImportExportError: If SQLAlchemy cannot be imported.
            如果无法导入 SQLAlchemy 则抛出 ImportExportError。
    Returns:
        The imported SQLAlchemy module.
        导入的 SQLAlchemy 模块。

    """
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
    """
    Ensure Polars is available.
    确保 Polars 可用。

    Raises:
        ImportExportError: If Polars cannot be imported.
            如果无法导入 Polars 则抛出 ImportExportError。
    Returns:
        The imported Polars module.
        导入的 Polars 模块。

    """
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
    """Field specification describing a SQLAlchemy column.
    字段规范，用于描述 SQLAlchemy 列。

    Attributes:
        name: Column name.
            列名。
        nullable: Whether column allows NULL.
            列是否允许 NULL。
        primary_key: Whether column is a primary key.
            是否为主键。
        has_default: Whether column has a client/server default.
            是否包含默认值（客户端/服务器端）。
        autoincrement: Whether this column autoincrements.
            是否自增。
        type_: SQLAlchemy column type.
            SQLAlchemy 列类型。
        python_type: Inferred Python type if available, else None.
            推断的 Python 类型（如果可用），否则为 None。
    """

    name: str
    nullable: bool
    primary_key: bool
    has_default: bool
    autoincrement: bool
    type_: Any
    python_type: type[Any] | None


def get_field_specs(model: Any) -> list[FieldSpec]:
    """Get field specifications from a SQLAlchemy model.
    从 SQLAlchemy 模型获取字段规范。

    Args:
        model: SQLAlchemy model class.
        model: SQLAlchemy 模型类。
    Returns:
        List of field specifications.
        字段规范列表。
    Raises:
        ImportExportError: If the model does not have a __table__ attribute.
            如果模型没有 __table__ 属性则抛出 ImportExportError。
    """
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
    """Check if a field specification represents an auto-incrementing primary key.
    检查字段规范是否表示一个自增主键。

    Args:
        spec: The field specification to check.
        spec: 要检查的字段规范。
    Returns:
        True if the field is an auto-incrementing primary key, False otherwise.
        如果字段是自增主键则返回 True，否则返回 False。
    """
    if not spec.primary_key:
        return False
    if spec.autoincrement:
        return True
    return spec.has_default


def resolve_import_specs(specs: list[FieldSpec], columns: list[str] | None) -> list[FieldSpec]:
    """Resolve import field specifications based on specified columns.
    根据指定的列解析导入字段规范。

    Args:
        specs: List of all field specifications.
        specs: 所有字段规范的列表。
        columns: List of column names to include, or None to include all.
        columns: 要包含的列名列表，或 None 表示包含所有列。
    Returns:
        List of field specifications to use for import.
        用于导入的字段规范列表。
    """
    if columns is not None:
        spec_map = {spec.name: spec for spec in specs}
        return [spec_map[name] for name in columns if name in spec_map]
    return [spec for spec in specs if not _is_auto_pk(spec)]


def resolve_export_specs(specs: list[FieldSpec], columns: list[str] | None) -> list[FieldSpec]:
    """Resolve export field specifications based on specified columns.
    根据指定的列解析导出字段规范。

    Args:
        specs: List of all field specifications.
        specs: 所有字段规范的列表。
        columns: List of column names to include, or None to include all.
        columns: 要包含的列名列表，或 None 表示包含所有列。
    Returns:
        List of field specifications to use for export.
        用于导出的字段规范列表。
    """
    if columns is not None:
        spec_map = {spec.name: spec for spec in specs}
        return [spec_map[name] for name in columns if name in spec_map]
    return list(specs)


def resolve_field_codecs(model: Any, specs: list[FieldSpec]) -> dict[str, Codec]:
    """Resolve field codecs for a SQLAlchemy model based on field specifications.
    根据字段规范解析 SQLAlchemy 模型的字段编解码器。

    Args:
        model: SQLAlchemy model class.
        model: SQLAlchemy 模型类。
        specs: List of field specifications.
        specs: 字段规范列表。
    Returns:
        Mapping from field name to Codec instance.
        字段名称到 Codec 实例的映射。
    """
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
    """Infer a Codec instance for a given field specification based on its type.
    根据字段规范的类型推断 Codec 实例。

    Args:
        sa: The SQLAlchemy module.
        sa: SQLAlchemy 模块。
        spec: The field specification.
        spec: 字段规范。
    Returns:
        A Codec instance if one can be inferred, or None otherwise.
        如果能推断出 Codec 实例则返回该实例，否则返回 None。
    """
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
    # Fallback to SQLAlchemy types / 回退到 SQLAlchemy 类型
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
    """Cast a basic value to the specified Python type.
        将基本值转换为指定的 Python 类型。

    Args:
        value: The value to cast.
        value: 要转换的值。
        python_type: The target Python type, or None to leave unchanged.
        python_type: 目标 Python 类型，或 None 表示保持不变。
    Returns:
        The cast value.
        转换后的值。
    """
    if python_type is None:
        return value
    if python_type is int:
        return int(str(value).strip())
    if python_type is float:
        return float(str(value).strip())
    return value
