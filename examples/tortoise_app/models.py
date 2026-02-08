"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: models.py
@DateTime: 2026-02-08
@Docs: Tortoise ORM model for Device.
Tortoise ORM 设备模型。
"""

from tortoise import fields
from tortoise.models import Model


class Device(Model):
    """Device table model.
    设备表模型。
    """

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100, unique=True)
    ip = fields.CharField(max_length=45)
    location = fields.CharField(max_length=200, null=True)

    class Meta:  # type: ignore[override]
        table = "devices"
