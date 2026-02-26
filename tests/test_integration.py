"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_integration.py
@DateTime: 2026-02-08
@Docs: Integration tests: full upload -> preview -> commit lifecycle.
集成测试：完整的上传 -> 预览 -> 提交生命周期。
"""

from pathlib import Path
from typing import Any

import pytest

from fastapi_import_export.config import ImportExportConfig
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import ImportExportService
from fastapi_import_export.storage_fs import ensure_dirs, get_import_paths, read_meta
from tests.conftest import make_upload_file


async def _validate_pass(db: Any, df: Any, *, allow_overwrite: bool = False) -> tuple[Any, list]:
    """Pass-through validator / 直通校验。"""
    return df, []


async def _persist(db: Any, valid_df: Any, *, allow_overwrite: bool = False) -> int:
    """Dummy persist / 虚拟落库。"""
    return int(valid_df.height)


@pytest.fixture
def svc(tmp_config: ImportExportConfig, mock_db: Any) -> ImportExportService:
    ensure_dirs(config=tmp_config)
    return ImportExportService(db=mock_db, config=tmp_config)


class TestCSVEndToEnd:
    """End-to-end CSV import test.
    CSV 端到端导入测试。
    """

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, svc: ImportExportService, tmp_config: ImportExportConfig) -> None:
        """Upload -> Preview -> Commit / 上传 -> 预览 -> 提交。"""
        csv = "name,email\nalice,alice@b.com\nbob,bob@b.com\n"
        file = make_upload_file("test.csv", csv.encode())

        # Step 1: Upload / Parse / Validate
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        assert validate_resp.total_rows == 2
        assert validate_resp.valid_rows == 2
        assert validate_resp.error_rows == 0

        # Step 2: Preview
        preview_resp = await svc.preview(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            page=1,
            page_size=50,
            kind="all",
        )
        assert preview_resp.total_rows == 2
        assert len(preview_resp.rows) == 2

        # Step 3: Commit
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        commit_resp = await svc.commit(body=body, persist_fn=_persist)
        assert commit_resp.status == "committed"
        assert commit_resp.imported_rows == 2

        # Verify meta on disk / 验证磁盘上的 meta
        paths = get_import_paths(validate_resp.import_id, config=tmp_config)
        meta = read_meta(paths)
        assert meta["status"] == "committed"


class TestXLSXEndToEnd:
    """End-to-end XLSX import test.
    XLSX 端到端导入测试。
    """

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, svc: ImportExportService, sample_xlsx_path: Path) -> None:
        """Upload XLSX -> Preview -> Commit / 上传 XLSX -> 预览 -> 提交。"""
        content = sample_xlsx_path.read_bytes()
        file = make_upload_file(
            "sample.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        assert validate_resp.total_rows == 5

        # Preview valid only
        preview_resp = await svc.preview(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            page=1,
            page_size=2,
            kind="valid",
        )
        assert preview_resp.total_rows == 5
        assert len(preview_resp.rows) == 2  # page_size=2

        # Commit
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        commit_resp = await svc.commit(body=body, persist_fn=_persist)
        assert commit_resp.status == "committed"


class TestHeaderOnlyFile:
    """Test file with only headers (no data rows).
    仅有表头（无数据行）的文件测试。
    """

    @pytest.mark.asyncio
    async def test_header_only_csv(self, svc: ImportExportService) -> None:
        """CSV with only headers / 仅含表头的 CSV。"""
        csv = "name,email\n"
        file = make_upload_file("headers_only.csv", csv.encode())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        assert validate_resp.total_rows == 0


class TestChineseHeadersImport:
    """Test import with Chinese headers.
    中文表头导入测试。
    """

    @pytest.mark.asyncio
    async def test_chinese_headers_with_aliases(self, svc: ImportExportService) -> None:
        """Chinese headers mapped via column_aliases / 中文表头通过 column_aliases 映射。"""
        csv = "用户名,邮箱,年龄\nalice,a@b.com,25\n"
        file = make_upload_file("cn.csv", csv.encode())
        validate_resp = await svc.upload_parse_validate(
            file=file,
            column_aliases={"用户名": "username", "邮箱": "email", "年龄": "age"},
            validate_fn=_validate_pass,
        )
        assert validate_resp.total_rows == 1
        assert validate_resp.valid_rows == 1


class TestLifecycleMatrix:
    """Lifecycle matrix tests for format and overwrite mode.
    针对格式与覆盖策略的生命周期矩阵测试。
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    @pytest.mark.parametrize("overwrite_mode", ["reject", "upsert", "replace"])
    async def test_format_overwrite_mode_matrix(
        self,
        svc: ImportExportService,
        tmp_config: ImportExportConfig,
        sample_xlsx_path: Path,
        fmt: str,
        overwrite_mode: str,
    ) -> None:
        """Validate preview and commit should work across format x overwrite_mode matrix.
        validate/preview/commit 在 format x overwrite_mode 矩阵下应稳定工作。
        """
        if fmt == "csv":
            file = make_upload_file("matrix.csv", b"name,email\nalice,alice@b.com\nbob,bob@b.com\n")
            expected_rows = 2
        else:
            file = make_upload_file(
                "matrix.xlsx",
                sample_xlsx_path.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            expected_rows = 5

        validate_resp = await svc.upload_parse_validate(
            file=file,
            column_aliases={},
            validate_fn=_validate_pass,
            overwrite_mode=overwrite_mode,
        )
        assert validate_resp.total_rows == expected_rows

        preview_resp = await svc.preview(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            page=1,
            page_size=2,
            kind="all",
        )
        assert preview_resp.total_rows == expected_rows

        commit_resp = await svc.commit(
            body=ImportCommitRequest(
                import_id=validate_resp.import_id,
                checksum=validate_resp.checksum,
                overwrite_mode=overwrite_mode,
            ),
            persist_fn=_persist,
        )
        assert commit_resp.status == "committed"
        assert commit_resp.imported_rows == expected_rows

        paths = get_import_paths(validate_resp.import_id, config=tmp_config)
        meta = read_meta(paths)
        assert meta.get("overwrite_mode") == overwrite_mode

    @pytest.mark.asyncio
    async def test_csv_with_utf8_bom(self, svc: ImportExportService) -> None:
        """UTF-8 BOM CSV should be parsed correctly / UTF-8 BOM 的 CSV 应被正确解析。"""
        csv_with_bom = b"\xef\xbb\xbfname,email\nalice,alice@b.com\n"
        file = make_upload_file("bom.csv", csv_with_bom)
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_validate_pass)
        assert validate_resp.total_rows == 1
        assert validate_resp.valid_rows == 1
