"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_service.py
@DateTime: 2026-02-08
@Docs: Tests for service.py module (core service).
service.py 模块测试（核心服务）。
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import polars as pl
import pytest

from fastapi_import_export.config import ImportExportConfig
from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import (
    ExportResult,
    ImportExportService,
    _find_conflict_row_numbers,
    _maybe_await,
    _parse_pg_unique_detail,
)
from fastapi_import_export.storage_fs import (
    ensure_dirs,
)
from tests.conftest import make_upload_file

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc(tmp_config: ImportExportConfig, mock_db: Any) -> ImportExportService:
    """ImportExportService with tmp_config / 使用 tmp_config 的 ImportExportService。"""
    ensure_dirs(config=tmp_config)
    return ImportExportService(db=mock_db, config=tmp_config)


@pytest.fixture
def svc_with_redis(tmp_config: ImportExportConfig, mock_db: Any, mock_redis: Any) -> ImportExportService:
    """ImportExportService with Redis / 带 Redis 的 ImportExportService。"""
    ensure_dirs(config=tmp_config)
    return ImportExportService(db=mock_db, config=tmp_config, redis_client=mock_redis)


def _csv_bytes(rows: int = 3) -> bytes:
    """Generate simple CSV bytes / 生成简单 CSV 字节。"""
    lines = ["username,email,age"]
    for i in range(1, rows + 1):
        lines.append(f"user{i},user{i}@example.com,{20 + i}")
    return "\n".join(lines).encode("utf-8")


async def _dummy_validate(db: Any, df: Any, *, allow_overwrite: bool = False) -> tuple[Any, list]:
    """Dummy validate_fn that passes all rows / 虚拟校验函数（所有行通过）。"""
    return df, []


async def _dummy_persist(db: Any, valid_df: Any, *, allow_overwrite: bool = False) -> int:
    """Dummy persist_fn / 虚拟落库函数。"""
    return int(valid_df.height)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestMaybeAwait:
    """Tests for _maybe_await.
    _maybe_await 测试。
    """

    @pytest.mark.asyncio
    async def test_sync_value(self) -> None:
        """Return sync value as-is / 同步值直接返回。"""
        result = await _maybe_await(42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_async_value(self) -> None:
        """Await async value / 异步值 await 后返回。"""

        async def coro():
            return "hello"

        result = await _maybe_await(coro())
        assert result == "hello"


class TestParsePgUniqueDetail:
    """Tests for _parse_pg_unique_detail.
    _parse_pg_unique_detail 测试。
    """

    def test_pg_format(self) -> None:
        """Parse PG format / 解析 PG 格式。"""
        text = "Key (email)=(alice@b.com) already exists."
        result = _parse_pg_unique_detail(text)
        assert result is not None
        assert result["columns"] == ["email"]
        assert result["values"] == ["alice@b.com"]

    def test_composite_key(self) -> None:
        """Parse composite key / 解析复合 key。"""
        text = "Key (name, email)=(alice, alice@b.com) already exists."
        result = _parse_pg_unique_detail(text)
        assert result is not None
        assert len(result["columns"]) == 2

    def test_non_pg_format(self) -> None:
        """Non-PG format returns None / 非 PG 格式返回 None。"""
        result = _parse_pg_unique_detail("some random error text")
        assert result is None


class TestFindConflictRowNumbers:
    """Tests for _find_conflict_row_numbers.
    _find_conflict_row_numbers 测试。
    """

    def test_finds_rows(self) -> None:
        """Find matching row numbers / 找到匹配的行号。"""
        df = pl.DataFrame(
            {
                "row_number": [1, 2, 3],
                "email": ["a@b.com", "c@d.com", "a@b.com"],
            }
        )
        result = _find_conflict_row_numbers(df, columns=["email"], values=["a@b.com"])
        assert result == [1, 3]

    def test_empty_df(self) -> None:
        """Empty DataFrame returns empty / 空 DataFrame 返回空列表。"""
        df = pl.DataFrame({"row_number": [], "email": []}).cast({"row_number": pl.Int64, "email": pl.Utf8})
        result = _find_conflict_row_numbers(df, columns=["email"], values=["a"])
        assert result == []

    def test_column_not_exists(self) -> None:
        """Missing column returns empty / 列不存在返回空列表。"""
        df = pl.DataFrame({"row_number": [1], "name": ["alice"]})
        result = _find_conflict_row_numbers(df, columns=["email"], values=["a"])
        assert result == []

    def test_missing_row_number_column(self) -> None:
        """Missing row_number column returns empty / 缺少 row_number 列返回空列表。"""
        df = pl.DataFrame({"email": ["a@b.com"]})
        result = _find_conflict_row_numbers(df, columns=["email"], values=["a@b.com"])
        assert result == []


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------


class TestExportTable:
    """Tests for export_table.
    export_table 测试。
    """

    @pytest.mark.asyncio
    async def test_csv_export(self, svc: ImportExportService) -> None:
        """Export CSV / 导出 CSV。"""

        async def df_fn(db: Any) -> pl.DataFrame:
            return pl.DataFrame({"name": ["alice", "bob"], "age": [25, 30]})

        result = await svc.export_table(fmt="csv", filename_prefix="users", df_fn=df_fn)
        assert isinstance(result, ExportResult)
        assert result.filename.endswith(".csv")
        assert "text/csv" in result.media_type
        assert result.path.exists()

    @pytest.mark.asyncio
    async def test_xlsx_export(self, svc: ImportExportService) -> None:
        """Export XLSX / 导出 XLSX。"""

        async def df_fn(db: Any) -> pl.DataFrame:
            return pl.DataFrame({"name": ["alice"]})

        result = await svc.export_table(fmt="xlsx", filename_prefix="users", df_fn=df_fn)
        assert result.filename.endswith(".xlsx")
        assert result.path.exists()

    @pytest.mark.asyncio
    async def test_build_template(self, svc: ImportExportService) -> None:
        """build_template calls builder / build_template 调用 builder。"""
        called: dict[str, Path | None] = {"path": None}

        def builder(path: Path) -> None:
            called["path"] = path
            path.write_bytes(b"template")

        result = await svc.build_template(filename_prefix="tpl", builder=builder)
        assert called["path"] is not None
        assert result.filename.endswith(".xlsx")


# ---------------------------------------------------------------------------
# Upload / Parse / Validate tests
# ---------------------------------------------------------------------------


class TestUploadParseValidate:
    """Tests for upload_parse_validate.
    upload_parse_validate 测试。
    """

    @pytest.mark.asyncio
    async def test_normal_flow(self, svc: ImportExportService) -> None:
        """Normal upload/parse/validate flow / 正常上传/解析/校验流程。"""
        file = make_upload_file("test.csv", _csv_bytes())
        resp = await svc.upload_parse_validate(
            file=file,
            column_aliases={},
            validate_fn=_dummy_validate,
        )
        assert resp.total_rows == 3
        assert resp.valid_rows == 3
        assert resp.error_rows == 0

    @pytest.mark.asyncio
    async def test_with_validation_errors(self, svc: ImportExportService) -> None:
        """Validation errors are reported / 校验错误被正确报告。"""

        async def validate_with_errors(db, df, *, allow_overwrite=False):
            errors = [{"row_number": 1, "field": "email", "message": "invalid"}]
            # Remove first row from valid_df / 从有效 df 中移除第一行
            valid_df = df.filter(pl.col("row_number") != 1) if "row_number" in df.columns else df
            return valid_df, errors

        file = make_upload_file("test.csv", _csv_bytes())
        resp = await svc.upload_parse_validate(
            file=file,
            column_aliases={},
            validate_fn=validate_with_errors,
        )
        assert resp.error_rows >= 1
        assert len(resp.errors) >= 1

    @pytest.mark.asyncio
    async def test_unique_fields_detection(self, svc: ImportExportService) -> None:
        """In-file duplicates detected / 文件内重复被检测。"""
        csv = "email\na@b.com\na@b.com\nc@d.com\n"
        file = make_upload_file("dup.csv", csv.encode())
        resp = await svc.upload_parse_validate(
            file=file,
            column_aliases={},
            validate_fn=_dummy_validate,
            unique_fields=["email"],
        )
        assert resp.error_rows >= 1

    @pytest.mark.asyncio
    async def test_file_too_large(self, tmp_config: ImportExportConfig, mock_db: Any) -> None:
        """File too large raises 413 / 文件过大抛出 413。"""
        ensure_dirs(config=tmp_config)
        svc = ImportExportService(db=mock_db, config=tmp_config, max_upload_mb=0)
        file = make_upload_file("big.csv", _csv_bytes())
        with pytest.raises(ImportExportError) as exc_info:
            await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_extension_rejected(self, svc: ImportExportService) -> None:
        """Disallowed extension raises 415 / 不允许的扩展名抛出 415。"""
        file = make_upload_file("data.exe", b"bad data", "application/octet-stream")
        with pytest.raises(ImportExportError) as exc_info:
            await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        assert exc_info.value.status_code == 415

    @pytest.mark.asyncio
    async def test_mime_rejected(self, svc: ImportExportService) -> None:
        """Disallowed MIME type raises 415 / 不允许的 MIME 类型抛出 415。"""
        file = make_upload_file("data.csv", b"data", "application/octet-stream")
        with pytest.raises(ImportExportError) as exc_info:
            await svc.upload_parse_validate(
                file=file,
                column_aliases={},
                validate_fn=_dummy_validate,
                allowed_mime_types=["text/csv"],
            )
        assert exc_info.value.status_code == 415


# ---------------------------------------------------------------------------
# Preview tests
# ---------------------------------------------------------------------------


class TestPreview:
    """Tests for preview.
    preview 测试。
    """

    @pytest.mark.asyncio
    async def test_preview_all(self, svc: ImportExportService) -> None:
        """Preview all parsed rows / 预览所有解析行。"""
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        resp = await svc.preview(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            page=1,
            page_size=50,
            kind="all",
        )
        assert resp.total_rows == 3
        assert len(resp.rows) == 3

    @pytest.mark.asyncio
    async def test_preview_valid(self, svc: ImportExportService) -> None:
        """Preview valid rows / 预览有效行。"""
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        resp = await svc.preview(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            page=1,
            page_size=50,
            kind="valid",
        )
        assert resp.total_rows == 3

    @pytest.mark.asyncio
    async def test_preview_checksum_mismatch(self, svc: ImportExportService) -> None:
        """Checksum mismatch raises error / checksum 不匹配抛出错误。"""
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        with pytest.raises(ImportExportError, match="checksum"):
            await svc.preview(
                import_id=validate_resp.import_id,
                checksum="wrong_checksum",
                page=1,
                page_size=50,
                kind="all",
            )


# ---------------------------------------------------------------------------
# Commit tests
# ---------------------------------------------------------------------------


class TestCommit:
    """Tests for commit.
    commit 测试。
    """

    @pytest.mark.asyncio
    async def test_commit_success(self, svc: ImportExportService) -> None:
        """Successful commit / 成功提交。"""
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        resp = await svc.commit(body=body, persist_fn=_dummy_persist)
        assert resp.status == "committed"
        assert resp.imported_rows == 3

    @pytest.mark.asyncio
    async def test_commit_checksum_mismatch(self, svc: ImportExportService) -> None:
        """Checksum mismatch raises / checksum 不匹配抛出错误。"""
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum="wrong",
        )
        with pytest.raises(ImportExportError, match="checksum"):
            await svc.commit(body=body, persist_fn=_dummy_persist)

    @pytest.mark.asyncio
    async def test_commit_already_committed(self, svc: ImportExportService) -> None:
        """Already committed returns without re-committing / 已提交直接返回。"""
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        await svc.commit(body=body, persist_fn=_dummy_persist)
        # Second commit should return idempotently / 第二次提交应幂等返回
        resp2 = await svc.commit(body=body, persist_fn=_dummy_persist)
        assert resp2.status == "committed"

    @pytest.mark.asyncio
    async def test_commit_with_validation_errors_blocked(self, svc: ImportExportService) -> None:
        """Commit blocked when validation errors exist / 存在校验错误时阻止提交。"""

        async def validate_with_errors(db, df, *, allow_overwrite=False):
            errors = [{"row_number": 1, "field": "x", "message": "bad"}]
            return df.filter(pl.col("row_number") != 1), errors

        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=validate_with_errors)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        with pytest.raises(ImportExportError, match="error"):
            await svc.commit(body=body, persist_fn=_dummy_persist)

    @pytest.mark.asyncio
    async def test_commit_persist_exception_reraises(self, svc: ImportExportService) -> None:
        """Non-integrity exception re-raises / 非完整性异常直接 re-raise。"""

        async def bad_persist(db, valid_df, *, allow_overwrite=False):
            raise RuntimeError("connection lost")

        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        with pytest.raises(RuntimeError, match="connection lost"):
            await svc.commit(body=body, persist_fn=bad_persist)

    @pytest.mark.asyncio
    async def test_commit_duck_typing_integrity_error(self, svc: ImportExportService) -> None:
        """Duck-typed integrity error with .orig / 鸭子类型完整性错误（含 .orig）。"""

        async def integrity_persist(db, valid_df, *, allow_overwrite=False):
            exc = Exception("duplicate key value violates unique constraint")
            orig = MagicMock()
            orig.detail = "Key (email)=(alice@b.com) already exists."
            orig.constraint_name = "uq_email"
            exc.orig = orig  # type: ignore[attr-defined]
            raise exc

        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        with pytest.raises(ImportExportError, match="constraint"):
            await svc.commit(body=body, persist_fn=integrity_persist)

    @pytest.mark.asyncio
    async def test_commit_string_match_fallback(self, svc: ImportExportService) -> None:
        """String-matching fallback for duplicate key / 字符串匹配兜底。"""

        async def dup_persist(db, valid_df, *, allow_overwrite=False):
            raise Exception("duplicate key value violates unique constraint")

        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        with pytest.raises(ImportExportError, match="[Uu]nique"):
            await svc.commit(body=body, persist_fn=dup_persist)


# ---------------------------------------------------------------------------
# Redis lock tests
# ---------------------------------------------------------------------------


class TestRedisLock:
    """Tests for Redis locking in commit.
    commit 中 Redis 锁测试。
    """

    @pytest.mark.asyncio
    async def test_lock_acquired(self, svc_with_redis: ImportExportService, mock_redis: Any) -> None:
        """Lock acquired allows commit / 成功获取锁允许提交。"""
        mock_redis.set = MagicMock(return_value=True)
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc_with_redis.upload_parse_validate(
            file=file, column_aliases={}, validate_fn=_dummy_validate
        )
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        resp = await svc_with_redis.commit(body=body, persist_fn=_dummy_persist)
        assert resp.status == "committed"
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_failed(self, svc_with_redis: ImportExportService, mock_redis: Any) -> None:
        """Lock not acquired rejects commit / 获取锁失败拒绝提交。"""
        mock_redis.set = MagicMock(return_value=False)
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc_with_redis.upload_parse_validate(
            file=file, column_aliases={}, validate_fn=_dummy_validate
        )
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        with pytest.raises(ImportExportError, match="[Ii]mport in progress"):
            await svc_with_redis.commit(body=body, persist_fn=_dummy_persist)

    @pytest.mark.asyncio
    async def test_no_redis_no_lock(self, svc: ImportExportService) -> None:
        """No Redis means no lock / 无 Redis 无锁正常执行。"""
        file = make_upload_file("test.csv", _csv_bytes())
        validate_resp = await svc.upload_parse_validate(file=file, column_aliases={}, validate_fn=_dummy_validate)
        body = ImportCommitRequest(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
        )
        resp = await svc.commit(body=body, persist_fn=_dummy_persist)
        assert resp.status == "committed"
