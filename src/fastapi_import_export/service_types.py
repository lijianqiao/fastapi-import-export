"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: service_types.py
@DateTime: 2026-02-08
@Docs: Service-level protocols, type aliases, and data classes.
服务层协议、类型别名与数据类。

Extracted from service.py for separation of concerns.
从 service.py 中提取，分离职责。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastapi_import_export.typing import TableData


class RedisLike(Protocol):
    """A minimal Redis client protocol used for locking.

    用于锁的最小 Redis 客户端协议。

    The protocol is deliberately permissive to support various clients
    (e.g. redis-py asyncio client). Methods may return either direct values
    or awaitables.

    为了兼容不同 Redis 客户端，本协议刻意放宽签名限制；方法可以返回普通值
    或可 await 的对象。
    """

    def set(self, *args: Any, **kwargs: Any) -> Any:
        """Set a key-value pair.

        设置键值对。
        """
        ...

    def get(self, *args: Any, **kwargs: Any) -> Any:
        """Get a key value.

        获取键值。
        """
        ...

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """Delete a key.

        删除键。
        """
        ...


ExportDfFn = Callable[[Any], Awaitable[TableData]]
BuildTemplateFn = Callable[[Path], None]


class ServiceValidateFn(Protocol):
    """Service-level validation handler signature.

    服务层校验处理函数签名。

    Your domain should implement this to:
        - Check required columns.
          检查必需列。
        - Validate formats, enums, references.
          校验格式/枚举/引用关系等。
        - Optionally skip "already exists" errors when allow_overwrite=True.
          allow_overwrite=True 时可跳过"已存在"类错误。

    Note:
        This protocol is specific to ``ImportExportService``.
        For the generic ``Importer`` lifecycle, see ``fastapi_import_export.typing.ValidateFn``.

        此协议专用于 ``ImportExportService``。
        通用 ``Importer`` 生命周期请参考 ``fastapi_import_export.typing.ValidateFn``。

    Returns:
        valid_df: rows allowed to be imported (should keep `row_number`).
            可导入行（建议保留 `row_number`）。
        errors: list of error dicts, each should contain row_number/field/message.
            错误列表（建议包含 row_number/field/message）。
    """

    async def __call__(
        self,
        db: Any,
        df: TableData,
        *,
        allow_overwrite: bool = False,
    ) -> tuple[TableData, list[dict[str, Any]]]: ...


class ServicePersistFn(Protocol):
    """Service-level persistence handler signature.

    服务层落库处理函数签名。

    Your domain should implement this to insert/update rows in a single
    transaction (recommended) and return the number of affected rows.

    业务侧实现落库逻辑（建议单事务），并返回实际写入（新增/更新）的行数。

    Note:
        This protocol is specific to ``ImportExportService``.
        For the generic ``Importer`` lifecycle, see ``fastapi_import_export.typing.PersistFn``.

        此协议专用于 ``ImportExportService``。
        通用 ``Importer`` 生命周期请参考 ``fastapi_import_export.typing.PersistFn``。
    """

    async def __call__(
        self,
        db: Any,
        valid_df: TableData,
        *,
        allow_overwrite: bool = False,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Result of an export/template build.

    导出/模板生成结果。

    Attributes:
        path: File path on disk.
            文件路径。
        filename: Suggested download filename.
            建议的下载文件名。
        media_type: HTTP media type string.
            HTTP 媒体类型字符串。
    """

    path: Path
    filename: str
    media_type: str
