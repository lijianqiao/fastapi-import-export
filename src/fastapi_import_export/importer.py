"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: importer.py
@DateTime: 2026-02-08
@Docs: Importer abstraction with lifecycle hooks.
导入器抽象与生命周期钩子。
"""

from dataclasses import dataclass
from enum import StrEnum

from fastapi import UploadFile

from fastapi_import_export.resource import Resource
from fastapi_import_export.schemas import ImportErrorItem
from fastapi_import_export.typing import ParseFn, PersistFn, TransformFn, ValidateFn


class ImportStatus(StrEnum):
    """
    Import status enum.
    导入状态枚举。
    """

    VALIDATED = "validated"
    COMMITTED = "committed"


@dataclass(frozen=True, slots=True)
class ImportResult[TError: ImportErrorItem]:
    """
    Import result.
    导入结果。

    Attributes:
        status: Import status.
        status: 导入状态。
        imported_rows: Persisted rows count.
        imported_rows: 实际落库行数。
        errors: Validation errors.
        errors: 校验错误列表。
    """

    status: ImportStatus
    imported_rows: int
    errors: list[TError]


class Importer[TTable, TError: ImportErrorItem]:
    """
    Importer base class.
    导入器基类。

    This class defines the lifecycle hooks:
    parse -> validate -> transform -> persist.
    该类定义生命周期钩子：解析 -> 校验 -> 转换 -> 持久化。
    """

    def __init__(
        self,
        *,
        parser: ParseFn[TTable],
        validator: ValidateFn[TTable, TError],
        transformer: TransformFn[TTable],
        persister: PersistFn[TTable],
    ) -> None:
        """
        Initialize importer.
        初始化导入器。

        Args:
            parser: Parse function.
            parser: 解析函数。
            validator: Validate function.
            validator: 校验函数。
            transformer: Transform function.
            transformer: 转换函数。
            persister: Persist function.
            persister: 落库函数。
        """
        self._parser = parser
        self._validator = validator
        self._transformer = transformer
        self._persister = persister

    async def import_data(
        self,
        *,
        file: UploadFile,
        resource: type[Resource],
        allow_overwrite: bool = False,
    ) -> ImportResult[TError]:
        """
        Run the import lifecycle.
        执行导入生命周期。

        Args:
            file: FastAPI UploadFile.
            file: FastAPI 上传文件。
            resource: Resource class.
            resource: 资源类。
            allow_overwrite: Allow overwrite flag.
            allow_overwrite: 是否允许覆盖。

        Returns:
            ImportResult: Import result.
            ImportResult: 导入结果。
        """
        data = await self.parse(file=file, resource=resource)
        valid_data, errors = await self.validate(data=data, resource=resource, allow_overwrite=allow_overwrite)
        if errors:
            return ImportResult(status=ImportStatus.VALIDATED, imported_rows=0, errors=errors)
        transformed = await self.transform(data=valid_data, resource=resource)
        imported_rows = await self.persist(data=transformed, resource=resource, allow_overwrite=allow_overwrite)
        return ImportResult(status=ImportStatus.COMMITTED, imported_rows=imported_rows, errors=[])

    async def parse(self, *, file: UploadFile, resource: type[Resource]) -> TTable:
        """
        Parse uploaded file.
        解析上传文件。
        """
        return await self._parser(file=file, resource=resource)

    async def validate(
        self, *, data: TTable, resource: type[Resource], allow_overwrite: bool
    ) -> tuple[TTable, list[TError]]:
        """
        Validate parsed data.
        校验解析数据。
        """
        return await self._validator(data=data, resource=resource, allow_overwrite=allow_overwrite)

    async def transform(self, *, data: TTable, resource: type[Resource]) -> TTable:
        """
        Transform valid data.
        转换有效数据。
        """
        return await self._transformer(data=data, resource=resource)

    async def persist(self, *, data: TTable, resource: type[Resource], allow_overwrite: bool) -> int:
        """
        Persist transformed data.
        持久化转换后的数据。
        """
        return await self._persister(data=data, resource=resource, allow_overwrite=allow_overwrite)
