"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: conftest.py
@DateTime: 2026-02-08
@Docs: Shared test fixtures for the fastapi-import-export test suite.
测试套件的公共 fixtures。
"""

import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from fastapi import UploadFile

from fastapi_import_export.config import ImportExportConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_config(tmp_path: Path) -> ImportExportConfig:
    """Return an ImportExportConfig rooted at tmp_path.
    返回以 tmp_path 为根的 ImportExportConfig。
    """
    return ImportExportConfig(base_dir=tmp_path)


@pytest.fixture
def sample_csv_path() -> Path:
    """Path to sample.csv fixture.
    sample.csv 样本文件路径。
    """
    return FIXTURES_DIR / "sample.csv"


@pytest.fixture
def sample_xlsx_path() -> Path:
    """Path to sample.xlsx fixture.
    sample.xlsx 样本文件路径。
    """
    return FIXTURES_DIR / "sample.xlsx"


@pytest.fixture
def chinese_csv_path() -> Path:
    """Path to chinese_headers.csv fixture.
    chinese_headers.csv 样本文件路径。
    """
    return FIXTURES_DIR / "chinese_headers.csv"


@pytest.fixture
def empty_csv_path() -> Path:
    """Path to empty.csv fixture.
    empty.csv 样本文件路径。
    """
    return FIXTURES_DIR / "empty.csv"


def make_upload_file(filename: str, content: bytes, content_type: str = "text/csv") -> UploadFile:
    """Create a mock UploadFile from bytes.
    从字节内容创建模拟 UploadFile。

    Args:
        filename: File name / 文件名。
        content: File content bytes / 文件内容字节。
        content_type: MIME type / MIME 类型。

    Returns:
        UploadFile: Mock upload file / 模拟上传文件。
    """
    return UploadFile(file=io.BytesIO(content), filename=filename, size=len(content), headers=MagicMock(get=lambda k, d=None: content_type if k == "content-type" else d))


@pytest.fixture
def sample_upload_csv(sample_csv_path: Path) -> UploadFile:
    """UploadFile wrapping sample.csv.
    包装 sample.csv 的 UploadFile。
    """
    content = sample_csv_path.read_bytes()
    return make_upload_file("sample.csv", content, "text/csv")


@pytest.fixture
def sample_upload_xlsx(sample_xlsx_path: Path) -> UploadFile:
    """UploadFile wrapping sample.xlsx.
    包装 sample.xlsx 的 UploadFile。
    """
    content = sample_xlsx_path.read_bytes()
    return make_upload_file(
        "sample.xlsx",
        content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@pytest.fixture
def sample_polars_df() -> pl.DataFrame:
    """A small Polars DataFrame with row_number column for testing.
    用于测试的含 row_number 列的小型 Polars DataFrame。
    """
    return pl.DataFrame(
        {
            "row_number": [1, 2, 3, 4, 5],
            "username": ["alice", "bob", "charlie", "diana", "eve"],
            "email": [
                "alice@example.com",
                "bob@example.com",
                "charlie@example.com",
                "diana@example.com",
                "eve@example.com",
            ],
            "age": ["25", "30", "35", "28", "22"],
        }
    )


@pytest.fixture
def mock_db() -> Any:
    """A simple mock object simulating a database connection.
    模拟数据库连接的简单 mock 对象。
    """
    db = MagicMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_redis() -> Any:
    """A mock object implementing the RedisLike protocol.
    实现 RedisLike 协议的 mock 对象。
    """
    redis = MagicMock()
    redis.set = MagicMock(return_value=True)
    redis.get = MagicMock(return_value=None)
    redis.delete = MagicMock(return_value=1)
    return redis
