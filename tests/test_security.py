"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_security.py
@DateTime: 2026-02-08
@Docs: Security and boundary tests.
安全性与边界条件测试。
"""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from fastapi_import_export.config import ImportExportConfig
from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import ImportExportService
from fastapi_import_export.storage_fs import (
    create_export_path,
    ensure_dirs,
    get_import_paths,
    new_import_id,
)
from tests.conftest import make_upload_file


async def _validate_pass(db: Any, df: Any, *, allow_overwrite: bool = False) -> tuple[Any, list]:
    return df, []


async def _persist(db: Any, valid_df: Any, *, allow_overwrite: bool = False) -> int:
    return int(valid_df.height)


@pytest.fixture
def svc(tmp_config: ImportExportConfig, mock_db: Any) -> ImportExportService:
    ensure_dirs(config=tmp_config)
    return ImportExportService(db=mock_db, config=tmp_config)


class TestPathTraversal:
    """Path traversal attack tests.
    路径穿越攻击测试。
    """

    def test_linux_style_traversal(self, tmp_config: ImportExportConfig) -> None:
        """../../etc/passwd -> passwd / Linux 风格路径穿越。"""
        path = create_export_path("../../etc/passwd", config=tmp_config)
        assert path.name == "passwd"
        assert path.parent == tmp_config.exports_dir

    def test_windows_style_traversal(self, tmp_config: ImportExportConfig) -> None:
        """..\\..\\windows\\system32 -> system32 / Windows 风格路径穿越。"""
        path = create_export_path("..\\..\\windows\\system32", config=tmp_config)
        assert path.name == "system32"
        assert path.parent == tmp_config.exports_dir

    def test_empty_filename(self, tmp_config: ImportExportConfig) -> None:
        """Empty filename -> 'export' / 空文件名回退。"""
        path = create_export_path("", config=tmp_config)
        assert path.name == "export"


class TestMaliciousExtension:
    """Malicious file extension tests.
    恶意扩展名测试。
    """

    @pytest.mark.asyncio
    async def test_exe_extension_rejected(self, svc: ImportExportService) -> None:
        """.exe extension rejected / .exe 扩展名被拒绝。"""
        file = make_upload_file("payload.exe", b"MZ", "application/octet-stream")
        with pytest.raises(ImportExportError) as exc_info:
            await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        assert exc_info.value.status_code == 415

    @pytest.mark.asyncio
    async def test_bat_extension_rejected(self, svc: ImportExportService) -> None:
        """.bat extension rejected / .bat 扩展名被拒绝。"""
        file = make_upload_file("evil.bat", b"@echo off", "application/octet-stream")
        with pytest.raises(ImportExportError) as exc_info:
            await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        assert exc_info.value.status_code == 415


class TestOversizedFile:
    """Oversized file upload tests.
    超大文件上传测试。
    """

    @pytest.mark.asyncio
    async def test_large_file_rejected_413(self, tmp_config: ImportExportConfig, mock_db: Any) -> None:
        """File exceeding max_upload_mb rejected / 超过 max_upload_mb 的文件被拒绝。"""
        ensure_dirs(config=tmp_config)
        svc = ImportExportService(db=mock_db, config=tmp_config, max_upload_mb=0)
        file = make_upload_file("big.csv", b"a,b\n1,2", "text/csv")
        with pytest.raises(ImportExportError) as exc_info:
            await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        assert exc_info.value.status_code == 413


class TestChecksumTampering:
    """Checksum tampering tests.
    checksum 篡改测试。
    """

    @pytest.mark.asyncio
    async def test_preview_checksum_tampered(self, svc: ImportExportService) -> None:
        """Tampered checksum rejected in preview / 预览中篡改的 checksum 被拒绝。"""
        csv = "name\nalice\n"
        file = make_upload_file("test.csv", csv.encode())
        resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        with pytest.raises(ImportExportError, match="checksum"):
            await svc.preview(
                import_id=resp.import_id,
                checksum="tampered_checksum",
                page=1,
                page_size=10,
                kind="all",
            )

    @pytest.mark.asyncio
    async def test_commit_checksum_tampered(self, svc: ImportExportService) -> None:
        """Tampered checksum rejected in commit / 提交中篡改的 checksum 被拒绝。"""
        csv = "name\nalice\n"
        file = make_upload_file("test.csv", csv.encode())
        resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        body = ImportCommitRequest(import_id=resp.import_id, checksum="tampered")
        with pytest.raises(ImportExportError, match="checksum"):
            await svc.commit(body=body, persist_fn=_persist)


class TestRedisLockCompetition:
    """Redis lock competition tests.
    Redis 锁竞争测试。
    """

    @pytest.mark.asyncio
    async def test_lock_value_mismatch_no_release(self, tmp_config: ImportExportConfig, mock_db: Any) -> None:
        """Lock value mismatch prevents release / 锁值不匹配阻止释放。"""
        ensure_dirs(config=tmp_config)
        redis = MagicMock()
        redis.set = MagicMock(return_value=True)
        # get returns a different value (simulating another holder)
        # get 返回不同值（模拟另一个持有者）
        redis.get = MagicMock(return_value="another_holder_value")
        redis.delete = MagicMock()

        svc = ImportExportService(db=mock_db, config=tmp_config, redis_client=redis)
        csv = "name\nalice\n"
        file = make_upload_file("test.csv", csv.encode())
        resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        body = ImportCommitRequest(import_id=resp.import_id, checksum=resp.checksum)
        await svc.commit(body=body, persist_fn=_persist)

        # delete should NOT have been called since another holder has the lock
        # delete 不应被调用因为另一个持有者持有锁
        redis.delete.assert_not_called()


class TestCorruptedMeta:
    """Tests for corrupted or missing intermediate artifacts.
    损坏或缺失中间产物测试。
    """

    @pytest.mark.asyncio
    async def test_corrupted_meta_json(self, tmp_config: ImportExportConfig, mock_db: Any) -> None:
        """Corrupted meta.json handling / 损坏的 meta.json 处理。"""
        ensure_dirs(config=tmp_config)
        svc = ImportExportService(db=mock_db, config=tmp_config)
        uid = new_import_id()
        paths = get_import_paths(uid, config=tmp_config)
        paths.root.mkdir(parents=True, exist_ok=True)
        paths.meta.write_text("INVALID JSON!!!")

        with pytest.raises((json.JSONDecodeError, ImportExportError)):
            await svc.preview(
                import_id=uid,
                checksum="abc",
                page=1,
                page_size=10,
                kind="all",
            )
