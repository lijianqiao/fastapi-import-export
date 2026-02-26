"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: resource.py
@DateTime: 2026/02/15 20:25:37
@Docs: Base resource definition for import/export.
导入导出基础资源定义。
"""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from fastapi_import_export.codecs import Codec
from fastapi_import_export.resource_inference import (
    build_excluded_set,
    infer_model_fields,
    is_excluded,
)


class Resource(BaseModel):
    """
    Base model for import/export resource definitions.

    Field mapping is explicit to avoid implicit ORM coupling.

    字段映射是显式的，以避免隐式的 ORM 耦合。

    To define a resource, subclass and set `model` + optionally `field_aliases` or `export_aliases`.
    定义资源时，子类化并设置 `model` + 可选的 `field_aliases` 或 `export_aliases`。
    """

    model_config = ConfigDict(extra="ignore")

    field_aliases: ClassVar[dict[str, str]] = {}
    export_aliases: ClassVar[dict[str, str]] = {}
    field_codecs: ClassVar[dict[str, Codec]] = {}
    model: ClassVar[Any | None] = None
    exclude_fields: ClassVar[list[str]] = []

    @classmethod
    def field_mapping(cls) -> dict[str, str]:
        """Return explicit field mapping (input header -> canonical field).
        返回显式字段映射（输入表头 -> 规范字段）。

        Args:
            None
        Returns:
            dict[str, str]: Mapping of input header to canonical field name.
            dict[str, str]: 输入表头到规范字段名称的映射。

        """
        mapping = {name: name for name in cls.field_order()}
        mapping.update(cls.field_aliases)
        return mapping

    @classmethod
    def field_order(cls) -> list[str]:
        """Return field order for import/export.
        返回导入/导出字段顺序。

        If `model_fields` are declared, use them as the canonical field order.
        If not, infer field order from `model` and use that as canonical order.
        如果声明了 `model_fields`，则使用它们作为规范字段顺序。
        如果没有，则从 `model` 推断字段顺序，并将其用作规范顺序。

        Args:
            None
        Returns:
            list[str]: Ordered list of canonical field names.
            list[str]: 规范字段名称的有序列表。

        """
        declared = list(cls.model_fields.keys())
        if declared:
            return declared
        return cls._infer_model_fields()

    @classmethod
    def export_mapping(cls) -> dict[str, str]:
        """Return export mapping (canonical field -> output header).
        返回导出映射（规范字段 -> 输出表头）。

        Args:
            None
        Returns:
            dict[str, str]: Mapping of canonical field name to output header.
            dict[str, str]: 规范字段名称到输出表头的映射。

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
        """Return identity mapping for current field order.
        返回当前字段顺序的同一映射。

        Args:
            None
        Returns:
            dict[str, str]: Identity mapping of canonical field name to itself.
            dict[str, str]: 规范字段名称到自身的同一映射。

        """
        return {name: name for name in cls.field_order()}

    @classmethod
    def _infer_model_fields(cls) -> list[str]:
        """Infer fields from `model` when no explicit fields are declared.
        当没有声明显式字段时，从 `model` 推断字段。

        Args:
            None
        Returns:
            list[str]: List of inferred field names from the model.
            list[str]: 从模型推断的字段名称列表。

        """
        model = cls.model
        if model is None:
            return []
        return infer_model_fields(model, excluded=cls._excluded_set())

    @classmethod
    def _excluded_set(cls) -> set[str]:
        """Return excluded field set from defaults + class configuration.
        从默认值 + 类配置返回排除字段集合。

        Args:
            None
        Returns:
            set[str]: Set of field names to exclude from inference.
            set[str]: 要从推断中排除的字段名称集合。

        """
        return build_excluded_set(cls.exclude_fields)

    @classmethod
    def _is_excluded(cls, *, name: str, obj: Any, excluded: set[str]) -> bool:
        """Compatibility wrapper for exclusion predicate.
        排除谓词的兼容性包装。

        Args:
            name: Field name to check for exclusion.
            name: 要检查是否排除的字段名称。
            obj: Field object to check for exclusion attributes.
            obj: 要检查是否具有排除属性的字段对象。
            excluded: Set of field names to exclude.
            excluded: 要排除的字段名称集合。
        Returns:
            bool: True if the field should be excluded, False otherwise.
            bool: 如果字段应该被排除则返回 True，否则返回 False。

        """
        return is_excluded(name=name, obj=obj, excluded=excluded)
