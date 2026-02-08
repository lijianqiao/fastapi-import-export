"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: models.py
@DateTime: 2026-02-08
@Docs: SQLModel model for Device.
SQLModel 设备模型。
"""

from sqlmodel import Field, SQLModel


class Device(SQLModel, table=True):
    """Device table model.
    设备表模型。
    """

    __tablename__ = "devices"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True)
    ip: str = Field(max_length=45)
    location: str | None = Field(default=None, max_length=200)
