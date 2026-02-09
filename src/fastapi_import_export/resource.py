"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: resource.py
@DateTime: 2026-02-08
@Docs: Resource base model and field mapping hooks.
资源基类与字段映射钩子。
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


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

    @classmethod
    def field_mapping(cls) -> dict[str, str]:
        """
        Return the explicit field mapping.
        返回显式字段映射。

        Returns:
            dict[str, str]: Mapping from input header to resource field.
            dict[str, str]: 输入表头到资源字段的映射。
        """
        return dict(cls.field_aliases)

    @classmethod
    def export_mapping(cls) -> dict[str, str]:
        """
        Return export column mapping (field -> output header).
        返回导出字段映射（字段 -> 输出列名）。
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
        return {name: name for name in cls.model_fields.keys()}
