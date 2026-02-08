"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: exporter.py
@DateTime: 2026-02-08
@Docs: Exporter abstraction with streaming output.
导出器抽象与流式输出。
"""

from dataclasses import dataclass

from fastapi_import_export.resource import Resource
from fastapi_import_export.typing import ByteStream, QueryFn, RenderFn, SerializeFn


@dataclass(frozen=True, slots=True)
class ExportPayload:
    """
    Export payload.
    导出载荷。

    Attributes:
        filename: Suggested file name.
        filename: 建议文件名。
        media_type: HTTP media type.
        media_type: HTTP 媒体类型。
        stream: Byte stream.
        stream: 字节流。
    """

    filename: str
    media_type: str
    stream: ByteStream


class Exporter[TTable, TParams]:
    """
    Exporter base class.
    导出器基类。

    Lifecycle hooks: query -> serialize -> render.
    生命周期钩子：查询 -> 序列化 -> 渲染。
    """

    def __init__(
        self,
        *,
        query_fn: QueryFn[TTable, TParams],
        serialize_fn: SerializeFn[TTable],
        render_fn: RenderFn,
    ) -> None:
        """
        Initialize exporter.
        初始化导出器。

        Args:
            query_fn: Query function.
            query_fn: 查询函数。
            serialize_fn: Serialize function.
            serialize_fn: 序列化函数。
            render_fn: Render function.
            render_fn: 渲染函数。
        """
        self._query_fn = query_fn
        self._serialize_fn = serialize_fn
        self._render_fn = render_fn

    async def query(self, *, resource: type[Resource], params: TParams | None = None) -> TTable:
        """
        Query data for export.
        查询导出数据。

        Args:
            resource: Resource class.
                资源类。
            params: Optional query params.
                可选查询参数。

        Returns:
            TTable: Query result data.
            TTable: 查询结果数据。
        """
        return await self._query_fn(resource=resource, params=params)

    async def serialize(self, *, data: TTable, fmt: str) -> bytes:
        """
        Serialize data into bytes.
        将数据序列化为字节。

        Args:
            data: Source data to serialize.
                待序列化数据。
            fmt: Output format name.
                输出格式名称。

        Returns:
            bytes: Serialized bytes.
            bytes: 序列化后的字节。
        """
        return await self._serialize_fn(data=data, fmt=fmt)

    async def render(self, *, data: bytes, fmt: str) -> ByteStream:
        """
        Render bytes to stream.
        将字节渲染为流。

        Args:
            data: Serialized bytes.
                序列化后的字节。
            fmt: Output format name.
                输出格式名称。

        Returns:
            ByteStream: Byte stream.
            ByteStream: 字节流。
        """
        return await self._render_fn(data=data, fmt=fmt)

    async def stream(
        self,
        *,
        resource: type[Resource],
        fmt: str,
        filename: str,
        media_type: str,
        params: TParams | None = None,
    ) -> ExportPayload:
        """
        Run export lifecycle and return stream payload.
        执行导出生命周期并返回流式载荷。

        Args:
            resource: Resource class.
                资源类。
            fmt: Output format name.
                输出格式名称。
            filename: Suggested filename.
                建议文件名。
            media_type: HTTP media type.
                HTTP 媒体类型。
            params: Optional query params.
                可选查询参数。

        Returns:
            ExportPayload: Export stream payload.
            ExportPayload: 导出流式载荷。
        """
        data = await self.query(resource=resource, params=params)
        serialized = await self.serialize(data=data, fmt=fmt)
        stream = await self.render(data=serialized, fmt=fmt)
        return ExportPayload(filename=filename, media_type=media_type, stream=stream)
