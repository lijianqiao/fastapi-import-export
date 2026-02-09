"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-02-09
@Docs: Tortoise ORM contrib adapters.
Tortoise ORM 贡献适配层。
"""

from fastapi_import_export.contrib.tortoise.export_model import export_model_csv
from fastapi_import_export.contrib.tortoise.import_model import import_model_csv

__all__ = ["export_model_csv", "import_model_csv"]

