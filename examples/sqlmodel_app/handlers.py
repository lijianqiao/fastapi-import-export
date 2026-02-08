"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: handlers.py
@DateTime: 2026-02-08
@Docs: Domain handlers for SQLModel example.
SQLModel 示例的领域处理器。
"""

from typing import Any, ClassVar

import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from fastapi_import_export.resource import Resource
from fastapi_import_export.validation_extras import RowValidator

from .models import Device


class DeviceResource(Resource):
    """Device import resource definition.
    设备导入资源定义。
    """

    name: str
    ip: str
    location: str | None = None
    field_aliases: ClassVar[dict[str, str]] = {"设备名": "name", "IP地址": "ip", "位置": "location"}


async def validate_fn(
    db: AsyncSession,
    df: pl.DataFrame,
    *,
    allow_overwrite: bool = False,
) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
    """Validate device rows.
    校验设备行。
    """
    errors: list[dict[str, Any]] = []

    for row in df.to_dicts():
        rv = RowValidator(errors=errors, row_number=int(row.get("row_number", 0)), row=row)
        rv.not_blank("name", "Device name is required / 设备名必填")
        rv.not_blank("ip", "IP is required / IP 必填")
        rv.ip_address("ip", "Invalid IP address / IP 地址格式无效")

    error_rows = {e["row_number"] for e in errors}
    if error_rows and "row_number" in df.columns:
        valid_df = df.filter(~pl.col("row_number").is_in(list(error_rows)))
    else:
        valid_df = df

    return valid_df, errors


async def persist_fn(
    db: AsyncSession,
    valid_df: pl.DataFrame,
    *,
    allow_overwrite: bool = False,
) -> int:
    """Persist valid device rows using SQLModel.
    使用 SQLModel 持久化有效设备行。
    """
    rows = valid_df.to_dicts()
    devices = [Device(name=r["name"], ip=r["ip"], location=r.get("location") or None) for r in rows]
    if not devices:
        return 0
    db.add_all(devices)
    await db.commit()
    return len(devices)


async def df_fn(db: AsyncSession) -> pl.DataFrame:
    """Export all devices as a Polars DataFrame.
    导出所有设备为 Polars DataFrame。
    """
    result = await db.execute(select(Device))
    devices = result.scalars().all()
    return pl.DataFrame([{"name": d.name, "ip": d.ip, "location": d.location} for d in devices])
