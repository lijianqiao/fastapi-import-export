"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: renderers.py
@DateTime: 2026-02-09
@Docs: Byte stream render helpers.
字节流渲染辅助函数。
"""

from collections.abc import AsyncIterator


async def render_bytes(data: bytes) -> AsyncIterator[bytes]:
    """Render bytes as a single-chunk async stream.
    将字节渲染为单块异步流。
    """
    yield data


async def render_chunks(data: bytes, *, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
    """Render bytes as chunked async stream.
    将字节渲染为分块异步流。
    """
    size = max(int(chunk_size), 1)
    for i in range(0, len(data), size):
        yield data[i : i + size]
