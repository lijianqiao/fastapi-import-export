"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: typing.py
@DateTime: 2026-02-08
@Docs: Shared protocols and types for import/export.
导入导出共享协议与类型。
"""

from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any, ParamSpec, Protocol, TypeVar

from fastapi import UploadFile

from fastapi_import_export.resource import Resource
from fastapi_import_export.schemas import ImportErrorItem

P = ParamSpec("P")
TTable = TypeVar("TTable")
TTable_co = TypeVar("TTable_co", covariant=True)
TTable_contra = TypeVar("TTable_contra", contravariant=True)
TParams_contra = TypeVar("TParams_contra", contravariant=True)
TError = TypeVar("TError", bound=ImportErrorItem)

type TableData = Any
type ByteStream = AsyncIterable[bytes]


class AsyncCallable(Protocol[P, TTable_co]):
    """
    Async callable protocol.
    异步可调用协议。
    """

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> TTable_co: ...


class ParseFn(Protocol[TTable_co]):
    """
    Parse function protocol.
    解析函数协议。

    Args:
        file: FastAPI UploadFile.
        file: FastAPI 上传文件。
        resource: Resource class for mapping.
        resource: 用于字段映射的资源类。

    Returns:
        TableData: Parsed table data.
        TableData: 解析后的表格数据。
    """

    async def __call__(self, *, file: UploadFile, resource: type[Resource]) -> TTable_co: ...


class ValidateFn(Protocol[TTable, TError]):
    """
    Validate function protocol.
    校验函数协议。

    Returns:
        tuple[TableData, list[ImportErrorItem]]: Valid data and errors.
        tuple[TableData, list[ImportErrorItem]]: 通过校验的数据与错误列表。
    """

    async def __call__(
        self, *, data: TTable, resource: type[Resource], allow_overwrite: bool = False
    ) -> tuple[TTable, list[TError]]: ...


class TransformFn(Protocol[TTable]):
    """
    Transform function protocol.
    转换函数协议。

    Returns:
        TableData: Transformed data.
        TableData: 转换后的数据。
    """

    async def __call__(self, *, data: TTable, resource: type[Resource]) -> TTable: ...


class PersistFn(Protocol[TTable_contra]):
    """
    Persist function protocol.
    落库函数协议。

    Returns:
        int: Number of rows persisted.
        int: 实际落库行数。
    """

    async def __call__(
        self, *, data: TTable_contra, resource: type[Resource], allow_overwrite: bool = False
    ) -> int: ...


class QueryFn(Protocol[TTable_co, TParams_contra]):
    """
    Query function protocol.
    查询函数协议。

    Returns:
        TableData: Query result data.
        TableData: 查询结果数据。
    """

    async def __call__(self, *, resource: type[Resource], params: TParams_contra | None = None) -> TTable_co: ...


class SerializeFn(Protocol[TTable_contra]):
    """
    Serialize function protocol.
    序列化函数协议。

    Returns:
        bytes: Serialized bytes.
        bytes: 序列化后的字节数据。
    """

    async def __call__(self, *, data: TTable_contra, fmt: str) -> bytes: ...


class RenderFn(Protocol):
    """
    Render function protocol.
    渲染函数协议。

    Returns:
        ByteStream: Stream of bytes.
        ByteStream: 字节流输出。
    """

    async def __call__(self, *, data: bytes, fmt: str) -> ByteStream: ...


class BuildTemplateFn(Protocol):
    """
    Template builder protocol.
    模板构建协议。

    Args:
        path: Output file path.
        path: 模板文件路径。
    """

    def __call__(self, path: Path) -> None: ...
