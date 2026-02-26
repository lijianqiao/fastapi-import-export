"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: resource_inference.py
@DateTime: 2026/02/15 20:26:08
@Docs: Helpers for inferring model fields from ORM models.
基于 ORM 模型推断字段的辅助函数。
"""

from typing import Any

DEFAULT_EXCLUDED_FIELDS = {"id", "created_at", "updated_at", "deleted_at", "is_deleted", "deleted"}


def build_excluded_set(custom_fields: list[str]) -> set[str]:
    """Build excluded field set from defaults and resource custom values.
    从默认值和资源自定义值构建排除字段集合。

    Args:
        custom_fields: Custom field names to exclude.
            要排除的自定义字段名称列表。
    Returns:
        set[str]: Combined set of excluded field names.
            组合后的排除字段名称集合。

    """
    custom = {str(field).strip().lower() for field in custom_fields if str(field).strip()}
    return DEFAULT_EXCLUDED_FIELDS | custom


def is_excluded(*, name: str, obj: Any, excluded: set[str]) -> bool:
    """Return True when a model field should be excluded from inferred mapping.
    返回 True 表示模型字段应该从推断映射中排除。

    Rules:
        - Name is in excluded set
        - Field has primary key attribute (SQLAlchemy/Tortoise)
        - Field has generated attribute (Tortoise)
    规则:
        - 名称在排除集合中
        - 字段具有主键属性（SQLAlchemy/Tortoise）
        - 字段具有生成属性（Tortoise）

    Args:
        name: Field name.
            字段名称。
        obj: Field object (e.g. SQLAlchemy Column or Tortoise ModelField).
            字段对象（例如 SQLAlchemy Column 或 Tortoise ModelField）。
        excluded: Set of excluded field names.
            排除字段名称集合。
    Returns:
        bool: True if the field should be excluded, False otherwise.
            如果字段应该被排除则返回 True，否则返回 False。

    """
    key = name.strip().lower()
    if key in excluded:
        return True
    if getattr(obj, "primary_key", False) or getattr(obj, "pk", False):
        return True
    if getattr(obj, "generated", False):
        return True
    return False


def infer_model_fields(model: Any, *, excluded: set[str]) -> list[str]:
    """
    Infer field names from common ORM model shapes.
    从常见的 ORM 模型结构推断字段名称。

    Supported shapes:
    - SQLAlchemy/SQLModel: `model.__table__.columns`
    - Tortoise ORM: `model._meta.fields_map` (+ optional `fields_db_projection`)
    支持的结构:
    - SQLAlchemy/SQLModel: `model.__table__.columns`
    - Tortoise ORM: `model._meta.fields_map` (+ 可选的 `fields_db_projection`)

    Args:
        model: ORM model class.
            ORM 模型类。
        excluded: Set of field names to exclude.
            要排除的字段名称集合。
    Returns:
        list[str]: List of inferred field names.
    """
    fields: list[str] = []

    table = getattr(model, "__table__", None)
    columns = getattr(table, "columns", None) if table is not None else None
    if columns is not None:
        for column in list(columns):
            name = str(getattr(column, "name", "") or "").strip()
            if not name:
                continue
            if is_excluded(name=name, obj=column, excluded=excluded):
                continue
            fields.append(name)
        return fields

    meta = getattr(model, "_meta", None)
    fields_map = getattr(meta, "fields_map", None) if meta is not None else None
    if isinstance(fields_map, dict):
        projection = getattr(meta, "fields_db_projection", None)
        names = list(projection.keys()) if isinstance(projection, dict) and projection else list(fields_map.keys())
        for name in names:
            field = fields_map.get(name)
            if field is None:
                continue
            field_name = str(name).strip()
            if not field_name:
                continue
            if is_excluded(name=field_name, obj=field, excluded=excluded):
                continue
            fields.append(field_name)
        return fields

    return []
