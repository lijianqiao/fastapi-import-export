"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: resource.py
@DateTime: 2026-02-08
@Docs: Resource base model and field mapping hooks.
资源基类与字段映射钩子。
"""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from fastapi_import_export.codecs import Codec


class Resource(BaseModel):
    """
    Resource
    资源模型

    The base model for import/export resource definitions.
    导入导出资源定义的基础模型。

    Notes:
        Field mapping is explicit to avoid implicit ORM coupling.
        字段映射需显式定义，避免隐式 ORM 耦合。
    """

    model_config = ConfigDict(extra="ignore")

    field_aliases: ClassVar[dict[str, str]] = {}
    export_aliases: ClassVar[dict[str, str]] = {}
    field_codecs: ClassVar[dict[str, Codec]] = {}
    model: ClassVar[Any | None] = None
    exclude_fields: ClassVar[list[str]] = []

    @classmethod
    def field_mapping(cls) -> dict[str, str]:
        """
        Return the explicit field mapping.
        返回显式字段映射。

        Returns:
            dict[str, str]: Mapping from input header to resource field.
            dict[str, str]: 输入表头到资源字段的映射。
        """
        mapping = {name: name for name in cls.field_order()}
        mapping.update(cls.field_aliases)
        return mapping

    @classmethod
    def field_order(cls) -> list[str]:
        """
        Return the field order for import/export.
        返回导入导出的字段顺序。

        Returns:
            list[str]: List of field names in order.
            list[str]: 按顺序的字段名列表。
        """
        declared = list(cls.model_fields.keys())
        if declared:
            return declared
        return cls._infer_model_fields()

    @classmethod
    def export_mapping(cls) -> dict[str, str]:
        """
        Return export column mapping (field -> output header).
        返回导出字段映射（字段 -> 输出列名）。

        Returns:
            dict[str, str]: Mapping from resource field to output header.
            dict[str, str]: 资源字段到输出表头的映射。
        """
        if cls.export_aliases:
            return dict(cls.export_aliases)
        inverse: dict[str, str] = {}
        for header, field in cls.field_aliases.items():
            field_key = str(field).strip()
            if not field_key:
                continue
            if field_key in inverse and inverse[field_key] != header:
                return cls._identity_mapping()
            inverse[field_key] = header
        if inverse:
            return inverse
        return cls._identity_mapping()

    @classmethod
    def _identity_mapping(cls) -> dict[str, str]:
        """
        Return an identity mapping of field names.
        返回字段名的同一映射。

        Returns:
            dict[str, str]: Mapping where each field maps to itself.
            dict[str, str]: 每个字段映射到自身的映射。
        """
        return {name: name for name in cls.field_order()}

    @classmethod
    def _infer_model_fields(cls) -> list[str]:
        """Infer field names from the associated model if possible.
        如果可能，从关联模型推断字段名称。

        Returns:
            list[str]: Inferred field names from the model.
            list[str]: 从模型推断的字段名称。
        """
        model = cls.model
        if model is None:
            return []
        fields: list[str] = []
        excluded = cls._excluded_set()

        table = getattr(model, "__table__", None)
        columns = getattr(table, "columns", None) if table is not None else None
        if columns is not None:
            for col in list(columns):
                name = str(getattr(col, "name", "") or "").strip()
                if not name:
                    continue
                if cls._is_excluded(name=name, obj=col, excluded=excluded):
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
                if cls._is_excluded(name=field_name, obj=field, excluded=excluded):
                    continue
                fields.append(field_name)
            return fields

        return []

    @classmethod
    def _excluded_set(cls) -> set[str]:
        """Return a set of field names to exclude based on defaults and class configuration.
        根据默认值和类配置返回要排除的字段名称集合。

        Returns:
            set[str]: Set of field names to exclude.
            set[str]: 要排除的字段名称集合。
        """
        defaults = {"id", "created_at", "updated_at", "deleted_at", "is_deleted", "deleted"}
        custom = {str(f).strip().lower() for f in cls.exclude_fields if str(f).strip()}
        return defaults | custom

    @classmethod
    def _is_excluded(cls, *, name: str, obj: Any, excluded: set[str]) -> bool:
        """Determine if a field should be excluded based on name, object attributes, and exclusion set.
        根据名称、对象属性和排除集合确定字段是否应被排除。

        Args:
            name (str): The name of the field.
            obj (Any): The field object.
            excluded (set[str]): Set of field names to exclude.

        Returns:
            bool: True if the field should be excluded, False otherwise.
        """
        key = name.strip().lower()
        if key in excluded:
            return True
        if getattr(obj, "primary_key", False) or getattr(obj, "pk", False):
            return True
        if getattr(obj, "generated", False):
            return True
        return False
