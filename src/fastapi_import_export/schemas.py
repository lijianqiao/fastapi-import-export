"""Pydantic schemas for import/export workflow.
导入导出流程的 Pydantic 模型。

These schemas are intentionally domain-agnostic. Your business logic can add
its own detailed validation structures if needed, but the core workflow uses
the models here for standard responses.

本模块提供导入导出流程的通用 Pydantic 模型，尽量保持与业务无关。
业务侧可以在校验时返回更丰富的错误信息，但核心流程使用这里的标准模型。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ImportErrorItem(BaseModel):
    """Single validation error item.

    校验错误项。
    校验错误明细项。

    Attributes:
        row_number: Source file row number (1-based, excluding header).
            源文件行号（从 1 开始，不含表头）。
        field: Optional field/column name.
            字段/列名（可选）。
        message: Human readable error message.
            可读的错误描述。
    """

    row_number: int = Field(..., description="源文件行号（从 1 开始，不含表头）")
    field: str | None = Field(default=None, description="字段名（可选）")
    message: str = Field(..., description="错误原因")


class ImportValidateResponse(BaseModel):
    """Response returned by the upload+parse+validate step.

    上传+解析+校验步骤的响应。

    Attributes:
        import_id: Unique import identifier.
            导入任务 ID。
        checksum: SHA256 checksum of the uploaded file.
            上传文件的 SHA256 校验和。
        total_rows: Total data rows in the source file.
            源文件数据行总数。
        valid_rows: Rows that passed validation.
            通过校验的行数。
        error_rows: Rows that contain any validation errors.
            含错误的行数。
        errors: A truncated list of error details (implementation may return only first N).
            错误明细（实现可截断只返回前 N 条）。
    """

    import_id: UUID
    checksum: str
    total_rows: int
    valid_rows: int
    error_rows: int
    errors: list[ImportErrorItem] = Field(default_factory=list, description="错误明细（可分页/截断返回）")


class ImportPreviewRow(BaseModel):
    """Preview row returned by the preview endpoint.

    预览端点返回的预览行。

    Attributes:
        row_number: Source file row number.
            源文件行号。
        data: Row data (column -> value), excluding `row_number`.
            行数据（列名 -> 值），不包含 `row_number` 字段。
    """

    row_number: int
    data: dict[str, Any]


class ImportPreviewResponse(BaseModel):
    """Paginated preview response.

    分页预览响应。

    Attributes:
        import_id: Import identifier.
            导入任务 ID。
        checksum: Uploaded file checksum.
            上传文件 checksum。
        page: Current page number (1-based).
            当前页码（从 1 开始）。
        page_size: Page size.
            每页大小。
        total_rows: Total rows in the selected dataset.
            选定数据集（all/valid）的总行数。
        rows: Preview rows.
            预览行列表。
    """

    import_id: UUID
    checksum: str
    page: int
    page_size: int
    total_rows: int
    rows: list[ImportPreviewRow]


class ImportCommitRequest(BaseModel):
    """Commit request body.

    提交请求体。

    Attributes:
        import_id: Import identifier.
            导入任务 ID。
        checksum: Checksum must match the uploaded file, used as a guard.
            checksum 必须与上传文件一致，用于保护/校验。
        allow_overwrite: Whether to allow overwriting existing records (domain-defined).
            是否允许覆盖（由业务定义，例如按 IP 覆盖）。
    """

    import_id: UUID
    checksum: str
    allow_overwrite: bool = False


class ImportCommitResponse(BaseModel):
    """Commit response.

    提交响应。

    Attributes:
        import_id: Import identifier.
            导入任务 ID。
        checksum: Uploaded file checksum.
            上传文件 checksum。
        status: Status string (e.g. committed).
            状态字符串（例如 committed）。
        imported_rows: Number of rows created/updated by persistence handler.
            实际写入（新增/更新）的行数。
        created_at: Commit timestamp.
            提交时间。
    """

    import_id: UUID
    checksum: str
    status: str
    imported_rows: int
    created_at: datetime
