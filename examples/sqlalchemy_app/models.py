"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: models.py
@DateTime: 2026-02-08
@Docs: SQLAlchemy ORM model for Device.
SQLAlchemy ORM 设备模型。
"""

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. / SQLAlchemy 声明式基类。"""


class Device(Base):
    """Device table model.
    设备表模型。
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
