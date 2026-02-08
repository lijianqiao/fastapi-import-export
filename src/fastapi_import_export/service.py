"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: service.py
@DateTime: 2026-02-08
@Docs: Import/export service with reusable workflow helpers.
导入导出服务与可复用流程辅助。

Reusable import/export orchestration service for FastAPI projects.
导入导出流程的 FastAPI 服务类。

This module provides a domain-agnostic service class `ImportExportService` that
implements a common import/export workflow:

该模块提供了一个与域无关的服务类"ImportExportService"
实现通用的导入/导出工作流程：

        - Export a dataset to CSV/XLSX.
            导出数据集到 CSV/XLSX。
        - Build a template file (XLSX).
            生成模板（XLSX）。
        - Upload → parse → validate (persist intermediate artifacts on disk).
            上传 → 解析 → 校验（并把中间产物落盘）。
        - Preview parsed/valid rows.
            预览解析后/校验通过的数据。
        - Commit import in a single transaction and optional Redis lock.
            单事务提交导入，并可选 Redis 锁防并发提交。

This library intentionally depends on FastAPI's `UploadFile` because it targets
FastAPI reuse. Python stdlib does not provide a built-in `UploadFile` type.

本库依赖 FastAPI 的 `UploadFile`（目标就是 FastAPI 复用）。Python 标准库
没有内置的 `UploadFile` 类型；如果要做框架无关版本，通常会用 `BinaryIO`/bytes
或 file-like objects 来抽象上传文件。
"""

import inspect
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from fastapi import UploadFile

from fastapi_import_export.config import ImportExportConfig, resolve_config
from fastapi_import_export.constraint_parser import is_unique_constraint_error, raise_unique_conflict
from fastapi_import_export.db_validation import DbCheckSpec, run_db_checks
from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.parse import normalize_columns, parse_tabular_file
from fastapi_import_export.schemas import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportErrorItem,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportValidateResponse,
)
from fastapi_import_export.service_types import (
    BuildTemplateFn,
    ExportDfFn,
    ExportResult,
    RedisLike,
    ServicePersistFn,
    ServiceValidateFn,
)
from fastapi_import_export.storage import (
    create_export_path,
    get_import_paths,
    new_import_id,
    now_ts,
    read_meta,
    safe_rmtree,
    sha256_file,
    write_meta,
)
from fastapi_import_export.validation import collect_infile_duplicates


def _require_polars() -> Any:
    try:
        import polars as pl

        return pl
    except Exception as exc:  # pragma: no cover / 覆盖忽略
        raise ImportExportError(
            message="Missing optional dependency: polars / 缺少可选依赖: polars",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


def _require_openpyxl() -> Any:
    try:
        from openpyxl import Workbook

        return Workbook
    except Exception as exc:  # pragma: no cover / 覆盖忽略
        raise ImportExportError(
            message="Missing optional dependency: openpyxl / 缺少可选依赖: openpyxl",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


async def _maybe_await(value: Any) -> Any:
    """Await a value if it is awaitable, otherwise return it as-is.

    如果是 awaitable，await 后返回；否则直接返回。

    Args:
        value: Any value or awaitable.
            任意值或 awaitable。

    Returns:
        Resolved value.
            解析后的值。
    """
    if inspect.isawaitable(value):
        return await value
    return value


class ImportExportService:
    """Domain-agnostic import/export service.

    与域无关的导入/导出服务类。

    This class holds:
        - a `db` object (passed through to handlers),
          db 对象（原样传递给 handler）
        - an optional Redis client for locking,
          可选 Redis 客户端用于加锁
        - a filesystem config for import/export workspace.
          导入导出工作区文件系统配置

    Examples:
        Basic usage / 基本用法:

        >>> from fastapi_import_export import ImportExportService
        >>> svc = ImportExportService(db=object())

        With custom base_dir / 指定 base_dir:

        >>> svc = ImportExportService(db=object(), base_dir="D:/tmp/import-export")
    """

    def __init__(
        self,
        *,
        db: Any,
        redis_client: RedisLike | None = None,
        config: ImportExportConfig | None = None,
        base_dir: str | None = None,
        max_upload_mb: int = 20,
        lock_ttl_seconds: int = 300,
    ):
        """
        Initialize the import/export service.
        初始化导入导出服务。

        Args:
            db: Database object passed through to handlers.
                数据库对象（会原样传递给 handler）。
            redis_client: Optional Redis client for locking.
                Redis 客户端（可选，用于加锁）。
            config: Optional import/export config.
                导入导出配置（可选）。
            base_dir: Optional base dir override for config.
                工作目录根路径（可选，会覆盖 config.base_dir）。
            max_upload_mb: Max upload size in MB.
                最大上传文件大小（MB，默认 20）。
            lock_ttl_seconds: Redis lock TTL in seconds.
                Redis 锁 TTL（秒，默认 300）。
        """
        self.db = db
        self.redis_client = redis_client
        self.config = config or resolve_config(base_dir=base_dir)
        self.max_upload_mb = max_upload_mb
        self.lock_ttl_seconds = lock_ttl_seconds

    async def export_table(
        self,
        *,
        fmt: str,
        filename_prefix: str,
        df_fn: ExportDfFn,
    ) -> ExportResult:
        """Export a dataset to CSV or XLSX.

        导出数据集为 CSV 或 XLSX 文件。

        Args:
            fmt: Export format, typically "csv" or "xlsx".
                导出格式，通常为 "csv" 或 "xlsx"。
            filename_prefix: Prefix used to build a timestamped filename.
                文件名前缀（会拼接时间戳）。
            df_fn: Async function that returns a Polars DataFrame.
                异步函数：返回待导出的 Polars DataFrame。

        Returns:
            ExportResult: Export result with path/filename/media_type.
                包含 path/filename/media_type 的导出结果。

        Raises:
            RuntimeError: When Workbook.active is None (XLSX export).
                Workbook.active 为 None（XLSX 导出时）。

        Examples:
            >>> async def df_fn(_db):
            ...     import polars as pl
            ...     return pl.DataFrame([{"a": 1}])
            >>> # await svc.export_table(fmt="csv", filename_prefix="items", df_fn=df_fn)
        """
        df = await df_fn(self.db)
        ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{ts}.{fmt}"
        file_path = create_export_path(filename, config=self.config)

        if fmt == "csv":
            df.write_csv(file_path, include_bom=True, line_terminator="\r\n")
            return ExportResult(path=file_path, filename=filename, media_type="text/csv; charset=utf-8")

        Workbook = _require_openpyxl()
        wb = Workbook()
        ws = wb.active
        if ws is None:
            raise RuntimeError("Workbook.active is None / Workbook.active 为空")
        ws = cast(Any, ws)
        ws.title = filename_prefix

        headers = df.columns
        ws.append(headers)
        for row in df.to_dicts():
            ws.append([row.get(h, "") for h in headers])
        ws.freeze_panes = "A2"
        wb.save(file_path)

        return ExportResult(
            path=file_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    async def build_template(
        self,
        *,
        filename_prefix: str,
        builder: BuildTemplateFn,
    ) -> ExportResult:
        """Build an XLSX template file and return its export result.

        构建 XLSX 模板文件并返回导出结果。

        Args:
            filename_prefix: Prefix used to build the template filename.
                模板文件名前缀。
            builder: A function that writes an xlsx file to the given path.
                写模板文件的函数（入参为目标路径）。

        Returns:
            ExportResult: Export result with path/filename/media_type.
                包含 path/filename/media_type 的导出结果。
        """
        ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{ts}.xlsx"
        file_path = create_export_path(filename, config=self.config)
        builder(file_path)
        return ExportResult(
            path=file_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    async def upload_parse_validate(
        self,
        *,
        file: UploadFile,
        column_aliases: dict[str, str],
        validate_fn: ServiceValidateFn,
        allow_overwrite: bool = False,
        unique_fields: list[str] | None = None,
        db_checks: list[DbCheckSpec] | None = None,
        allowed_extensions: Iterable[str] | None = None,
        allowed_mime_types: Iterable[str] | None = None,
    ) -> ImportValidateResponse:
        """Upload, parse, normalize columns, then validate.

        上传、解析、归一化列，然后校验。

        Artifacts written / 写入的中间产物:
            - original file (with suffix)
              原始上传文件（带扩展名）
            - meta.json
              元信息
            - parsed.parquet
              解析后的全量数据
            - valid.parquet
              校验通过的数据
            - errors.json
              校验错误

        Args:
            file: FastAPI UploadFile.
                FastAPI UploadFile。
            column_aliases: Column mapping for header normalization.
                列名映射（用于表头归一）。
            validate_fn: Domain validation handler.
                业务校验 handler。
            allow_overwrite: Pass-through overwrite flag for domain logic.
                覆盖标志（透传给业务校验逻辑）。
            unique_fields: Unique fields to check within file.
                文件内唯一性检查字段列表。
            db_checks: Optional database check specs.
                可选数据库校验规范列表。
            allowed_extensions: Allowed upload file extensions.
                允许上传的文件扩展名。
            allowed_mime_types: Allowed upload MIME types.
                允许上传的 MIME 类型。

        Returns:
            ImportValidateResponse: Validation response.
                校验响应。

        Raises:
            ImportExportError: When uploaded file is too large.
                上传文件过大时抛出。
            ImportExportError: When file extension or content type is not allowed.
                文件扩展名或内容类型不被允许时抛出。
        """
        import_id = new_import_id()
        paths = get_import_paths(import_id, config=self.config)
        # Track whether parsing succeeded; only clean up the directory on
        # parse-stage failures. Validation-stage errors preserve artifacts
        # so the user can retry without re-uploading.
        # 跟踪解析阶段是否成功；仅在解析阶段失败时清理目录。
        # 校验阶段的错误保留中间产物，用户无需重新上传即可重试。
        parsed_ok = False
        try:
            paths.root.mkdir(parents=True, exist_ok=True)

            filename = file.filename or "upload"
            content_type = file.content_type
            ext = Path(filename).suffix.lower()
            allowed_exts = {
                v.strip().lower() for v in (allowed_extensions or self.config.allowed_extensions) if str(v).strip()
            }
            allowed_mimes = {
                v.strip().lower() for v in (allowed_mime_types or self.config.allowed_mime_types) if str(v).strip()
            }
            if allowed_exts and ext not in allowed_exts:
                raise ImportExportError(
                    message=f"Unsupported file extension: {ext} / 不支持的文件扩展名: {ext}",
                    status_code=415,
                    error_code="unsupported_media_type",
                )
            content_type_norm = str(content_type or "").strip().lower()
            if allowed_mimes and content_type_norm and content_type_norm not in allowed_mimes:
                raise ImportExportError(
                    message=(f"Unsupported content type: {content_type_norm} / 不支持的内容类型: {content_type_norm}"),
                    status_code=415,
                    error_code="unsupported_media_type",
                )
            original_path = paths.original.with_suffix(ext)

            size = 0
            with original_path.open("wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > int(self.max_upload_mb) * 1024 * 1024:
                        raise ImportExportError(message="File too large / 上传文件过大", status_code=413)
                    out.write(chunk)

            checksum = sha256_file(original_path)
            meta: dict[str, Any] = {
                "import_id": str(import_id),
                "filename": filename,
                "content_type": content_type,
                "checksum": checksum,
                "size_bytes": size,
                "created_at": now_ts(),
                "status": "uploaded",
            }
            write_meta(paths, meta)

            pl = _require_polars()
            parsed = parse_tabular_file(original_path, filename=filename)
            df = normalize_columns(parsed.df, column_aliases)
            df.write_parquet(paths.parsed_parquet)
            parsed_ok = True

            valid_df, errors = await validate_fn(self.db, df, allow_overwrite=allow_overwrite)
            if db_checks:
                errors.extend(await run_db_checks(db=self.db, df=df, specs=db_checks, allow_overwrite=allow_overwrite))
            if unique_fields:
                errors.extend(collect_infile_duplicates(df, unique_fields))
                extra_error_rows = {int(e.get("row_number") or 0) for e in errors if int(e.get("row_number") or 0) > 0}
                if not valid_df.is_empty() and extra_error_rows:
                    if "row_number" in valid_df.columns:
                        valid_df = valid_df.filter(~pl.col("row_number").is_in(list(extra_error_rows)))
            paths.errors_json.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
            if not valid_df.is_empty():
                valid_df.write_parquet(paths.valid_parquet)

            resp = ImportValidateResponse(
                import_id=import_id,
                checksum=checksum,
                total_rows=int(parsed.total_rows),
                valid_rows=int(valid_df.height) if not valid_df.is_empty() else 0,
                error_rows=len({e["row_number"] for e in errors if int(e.get("row_number") or 0) > 0}) if errors else 0,
                errors=[
                    ImportErrorItem(
                        row_number=int(e.get("row_number") or 0),
                        field=cast(str | None, e.get("field")),
                        message=str(e.get("message") or ""),
                    )
                    for e in errors[:200]
                ],
            )

            meta["status"] = "validated"
            meta["total_rows"] = resp.total_rows
            meta["valid_rows"] = resp.valid_rows
            meta["error_rows"] = resp.error_rows
            write_meta(paths, meta)
            return resp
        except Exception:
            if not parsed_ok:
                # Only clean up when parsing failed; preserve artifacts for
                # validation-stage retries.
                # 仅在解析阶段失败时清理；校验阶段失败保留中间产物以便重试。
                safe_rmtree(paths.root)
            raise

    async def preview(
        self,
        *,
        import_id: UUID,
        checksum: str,
        page: int,
        page_size: int,
        kind: str,
    ) -> ImportPreviewResponse:
        """Preview parsed or validated data.

        预览解析或校验后的数据。

        Args:
            import_id: Import job id.
                导入任务 ID。
            checksum: Must match meta.json checksum.
                必须与 meta.json 中 checksum 一致。
            page: Page number (1-based).
                页码（从 1 开始）。
            page_size: Page size.
                每页大小。
            kind: "all" uses parsed.parquet, "valid" uses valid.parquet.
                "all" 预览全量解析数据；"valid" 只预览通过校验的数据。

        Returns:
            ImportPreviewResponse: Preview response with rows.
                预览响应（包含 rows）。

        Raises:
            ImportExportError: When page/page_size/kind is invalid or checksum mismatches.
                page/page_size/kind 参数非法或 checksum 不匹配时抛出。
        """
        paths = get_import_paths(import_id, config=self.config)
        if page < 1:
            raise ImportExportError(message="page must be >= 1 / page 必须 >= 1")
        if page_size < 1 or page_size > 500:
            raise ImportExportError(message="page_size must be in 1..500 / page_size 必须在 1..500 之间")
        if kind not in {"all", "valid"}:
            raise ImportExportError(message="kind must be all or valid / kind 必须为 all 或 valid")
        meta = read_meta(paths)
        if str(meta.get("checksum")) != checksum:
            raise ImportExportError(message="checksum mismatch / checksum 不匹配")

        parquet = paths.valid_parquet if kind == "valid" else paths.parsed_parquet
        if not parquet.exists():
            return ImportPreviewResponse(
                import_id=import_id,
                checksum=checksum,
                page=page,
                page_size=page_size,
                total_rows=0,
                rows=[],
            )

        pl = _require_polars()
        df = pl.scan_parquet(parquet).slice((page - 1) * page_size, page_size).collect()
        total_rows = int(pl.scan_parquet(parquet).select(pl.len()).collect()[0, 0])
        rows: list[ImportPreviewRow] = []
        for r in df.to_dicts():
            row_number = int(r.get("row_number") or 0)
            data = {k: v for k, v in r.items() if k != "row_number"}
            rows.append(ImportPreviewRow(row_number=row_number, data=data))

        return ImportPreviewResponse(
            import_id=import_id,
            checksum=checksum,
            page=page,
            page_size=page_size,
            total_rows=total_rows,
            rows=rows,
        )

    async def commit(
        self,
        *,
        body: ImportCommitRequest,
        persist_fn: ServicePersistFn,
        lock_namespace: str = "import",
    ) -> ImportCommitResponse:
        """Commit an import job (single transaction recommended).

        提交导入任务（推荐单事务）。

        This method:
            - Ensures checksum matches.
              校验 checksum。
            - Ensures there are no validation errors.
              若存在 errors.json 且非空，则阻止提交。
            - Optionally acquires a Redis lock to prevent concurrent commits.
              可选：Redis 锁防止并发提交同一 import_id。
            - Calls `persist_fn(db, valid_df, allow_overwrite=...)`.
              调用业务落库函数。

        Note:
            Before calling ``persist_fn``, the service attempts to ``rollback()``
            the db session to ensure a clean transaction state. Callers should NOT
            have uncommitted changes on the same ``db`` session.

            在调用 ``persist_fn`` 前，服务会尝试对 db session 执行 ``rollback()``，
            以确保事务状态干净。调用方不应在同一 ``db`` session 上保留未提交的变更。

        Args:
            body: Commit request.
                提交请求体。
            persist_fn: Domain persistence handler.
                业务落库 handler。
            lock_namespace: Namespace prefix for lock key.
                锁 key 的命名空间前缀。

        Returns:
            ImportCommitResponse: Commit response with imported_rows.
                提交响应（包含 imported_rows）。

        Raises:
            ImportExportError: For empty/mismatched checksum, missing import_id, invalid status,
                existing validation errors, lock failure, or DB integrity error.
                checksum 为空/不匹配、import_id 不存在、状态非法、存在校验错误、锁获取失败或数据库完整性错误时抛出。
        """
        paths = get_import_paths(body.import_id, config=self.config)
        if not str(body.checksum).strip():
            raise ImportExportError(message="checksum cannot be empty / checksum 不能为空")
        if not paths.meta.exists():
            raise ImportExportError(message="import_id not found or expired / import_id 不存在或已过期")
        meta = read_meta(paths)
        if str(meta.get("checksum")) != body.checksum:
            raise ImportExportError(message="checksum mismatch / checksum 不匹配")
        if str(meta.get("status")) not in {"validated", "committed"}:
            raise ImportExportError(
                message="Invalid import status; complete validation first / 导入状态非法，请先完成上传校验"
            )

        if meta.get("status") == "committed":
            committed_at = int(meta.get("committed_at") or now_ts())
            return ImportCommitResponse(
                import_id=body.import_id,
                checksum=body.checksum,
                status="committed",
                imported_rows=int(meta.get("imported_rows") or 0),
                created_at=datetime.fromtimestamp(committed_at, tz=UTC),
            )

        if paths.errors_json.exists():
            errors = json.loads(paths.errors_json.read_text(encoding="utf-8"))
            if errors:
                raise ImportExportError(
                    message="Validation errors exist; batch import is blocked / 存在校验错误，整批不可导入",
                    details=errors[:200],
                )

        if not paths.valid_parquet.exists():
            raise ImportExportError(
                message="Validated data is missing; re-validate or re-upload / 校验数据缺失，请重新校验或重新上传",
                status_code=409,
            )

        lock_key = f"{lock_namespace}:lock:{body.import_id}"
        # Use a unique lock value so we only release our own lock.
        # 使用唯一锁值，确保仅释放自己持有的锁。
        lock_value = str(new_import_id())
        lock_acquired = False
        if self.redis_client is not None:
            result = await _maybe_await(self.redis_client.set(lock_key, lock_value, ex=self.lock_ttl_seconds, nx=True))
            lock_acquired = bool(result)
            if not lock_acquired:
                raise ImportExportError(message="Import in progress, retry later / 导入正在执行，请稍后重试")

        pl = _require_polars()
        valid_df = pl.read_parquet(paths.valid_parquet)
        # Ensure a clean transaction state before persisting.
        # 在落库前确保事务状态干净，避免残留的未提交操作干扰提交。
        rollback = getattr(self.db, "rollback", None)
        if callable(rollback):
            try:
                await _maybe_await(rollback())
            except Exception:
                pass

        try:
            imported_rows = await persist_fn(self.db, valid_df, allow_overwrite=body.allow_overwrite)
            meta["status"] = "committed"
            meta["committed_at"] = now_ts()
            meta["imported_rows"] = imported_rows
            write_meta(paths, meta)
            return ImportCommitResponse(
                import_id=body.import_id,
                checksum=body.checksum,
                status="committed",
                imported_rows=imported_rows,
                created_at=datetime.fromtimestamp(int(meta.get("committed_at") or now_ts()), tz=UTC),
            )
        except Exception as exc:
            meta["status"] = "commit_failed"
            meta["commit_failed_at"] = now_ts()
            meta["commit_error"] = str(exc)
            write_meta(paths, meta)

            # ORM-agnostic: use duck-typing to extract constraint details
            # from any ORM (e.g. SQLAlchemy .orig, Tortoise, raw driver, etc.).
            # ORM 无关：使用鸭子类型从任何 ORM 提取约束详情。
            text = str(exc)
            detail_text = ""
            extra_details: dict[str, Any] | None = None
            orig = getattr(exc, "orig", None)
            if orig is not None:
                constraint = getattr(orig, "constraint_name", None) or getattr(orig, "constraint", None)
                detail = getattr(orig, "detail", None)
                if constraint or detail:
                    extra_details = {}
                    if constraint:
                        extra_details["constraint"] = str(constraint)
                    if detail:
                        extra_details["detail"] = str(detail)
                        detail_text = str(detail)

            if is_unique_constraint_error(text, detail_text=detail_text):
                raise_unique_conflict(exc, valid_df, detail_text=detail_text, extra_details=extra_details)
            raise
        finally:
            if self.redis_client is not None and lock_acquired:
                try:
                    # Only delete if the lock value still matches ours.
                    # Non-atomic GET+DELETE; acceptable for this library scope.
                    # 仅在锁值仍为自己持有时删除。非原子 GET+DELETE；在本库范围内可接受。
                    current = await _maybe_await(self.redis_client.get(lock_key))
                    if current is not None and str(current) == lock_value:
                        await _maybe_await(self.redis_client.delete(lock_key))
                except Exception:
                    pass
