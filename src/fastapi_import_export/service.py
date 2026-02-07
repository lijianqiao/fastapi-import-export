"""Reusable import/export orchestration service for FastAPI projects.
导入导出流程的 FastAPI 服务类。

This module provides a domain-agnostic service class `ImportExportService` that
implements a common import/export workflow:

该模块提供了一个与域无关的服务类“ImportExportService”
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
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import polars as pl
from fastapi import UploadFile
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from fastapi_import_export.config import ImportExportConfig, resolve_config
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

try:
    from sqlalchemy.exc import IntegrityError
except Exception:  # pragma: no cover
    IntegrityError = None  # type: ignore


class RedisLike(Protocol):
    """A minimal Redis client protocol used for locking.

    用于锁的最小 Redis 客户端协议。

    The protocol is deliberately permissive to support various clients
    (e.g. redis-py asyncio client). Methods may return either direct values
    or awaitables.

    为了兼容不同 Redis 客户端，本协议刻意放宽签名限制；方法可以返回普通值
    或可 await 的对象。
    """

    def set(self, *args: Any, **kwargs: Any) -> Any: ...

    """Set a key-value pair.

    设置键值对。
    """

    def delete(self, *args: Any, **kwargs: Any) -> Any: ...

    """Delete a key.

    删除键。
    """


ExportDfFn = Callable[[Any], Awaitable[pl.DataFrame]]
BuildTemplateFn = Callable[[Path], None]


class ValidateFn(Protocol):
    """Validation handler signature.

    校验处理函数签名。

    Your domain should implement this to:
        - Check required columns.
          检查必需列。
        - Validate formats, enums, references.
          校验格式/枚举/引用关系等。
        - Optionally skip "already exists" errors when allow_overwrite=True.
          allow_overwrite=True 时可跳过“已存在”类错误。

    Returns:
        valid_df: rows allowed to be imported (should keep `row_number`).
            可导入行（建议保留 `row_number`）。
        errors: list of error dicts, each should contain row_number/field/message.
            错误列表（建议包含 row_number/field/message）。
    """

    async def __call__(
        self,
        db: Any,
        df: pl.DataFrame,
        *,
        allow_overwrite: bool = False,
    ) -> tuple[pl.DataFrame, list[dict[str, Any]]]: ...


class PersistFn(Protocol):
    """Persistence handler signature.

    落库处理函数签名。

    Your domain should implement this to insert/update rows in a single
    transaction (recommended) and return the number of affected rows.

    业务侧实现落库逻辑（建议单事务），并返回实际写入（新增/更新）的行数。
    """

    async def __call__(
        self,
        db: Any,
        valid_df: pl.DataFrame,
        *,
        allow_overwrite: bool = False,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Result of an export/template build.

    导出/模板生成结果。

    Attributes:
        path: File path on disk.
            文件路径。
        filename: Suggested download filename.
            建议的下载文件名。
        media_type: HTTP media type string.
            HTTP media_type。
    """

    path: Path
    filename: str
    media_type: str


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


def _format_integrity_error(exc: Exception) -> tuple[str, dict[str, Any] | None]:
    """Format an IntegrityError exception.

    格式化 IntegrityError 异常。

    Args:
        exc: The IntegrityError exception instance.
            IntegrityError 异常实例。

    Returns:
        A tuple of (user-friendly message, optional details dict).
            包含用户友好消息和可选详细信息字典的元组。
    """
    orig = getattr(exc, "orig", None)
    constraint = getattr(orig, "constraint_name", None) or getattr(orig, "constraint", None)
    detail = getattr(orig, "detail", None)
    msg = str(exc)
    details: dict[str, Any] = {}
    if constraint:
        details["constraint"] = str(constraint)
    if detail:
        details["detail"] = str(detail)
    if "duplicate key value violates unique constraint" in msg:
        user_msg = "唯一约束冲突：导入数据与现有数据存在重复键（可能包含软删除记录）。"
        if details:
            return user_msg, details
        return user_msg, None
    user_msg = "数据库完整性错误：导入写入失败。"
    return user_msg, details or None


def _parse_pg_unique_detail(text: str) -> dict[str, Any] | None:
    """Parse PostgreSQL unique constraint detail message.

    解析 PostgreSQL 唯一约束详细错误信息。

    Args:
        text: The detail message text.
            详细错误信息文本。

    Returns:
        A dict with "columns" and "values" keys, or None if not matched.
            包含 "columns" 和 "values" 键的字典，或 None（未匹配）。
    """
    m = re.search(r"Key\s+\((?P<cols>[^)]+)\)=\((?P<vals>[^)]+)\)\s+already exists\.", text)
    if not m:
        return None
    cols = [c.strip() for c in str(m.group("cols")).split(",") if c.strip()]
    vals = [v.strip() for v in str(m.group("vals")).split(",") if v.strip()]
    if len(cols) != len(vals):
        return {"columns": cols, "values": vals}
    return {"columns": cols, "values": vals}


def _find_conflict_row_numbers(
    df: pl.DataFrame, *, columns: list[str], values: list[str], limit: int = 50
) -> list[int]:
    """Find row numbers of rows with given column values.

    查找给定列值的行号。

    Args:
        df: The DataFrame to search.
            要搜索的 DataFrame。
        columns: List of column names to match.
            要匹配的列名列表。
        values: List of values to match.
            要匹配的值列表。
        limit: Maximum number of row numbers to return.
            返回的最大行号数量。

    Returns:
        A list of row numbers where the specified columns have the given values.
            指定列值匹配的行号列表。
    """
    if df.is_empty():
        return []
    for c in columns:
        if c not in df.columns:
            return []

    exprs: list[pl.Expr] = []
    for c, v in zip(columns, values, strict=False):
        exprs.append(pl.col(c).cast(pl.Utf8, strict=False) == v)
    if not exprs:
        return []
    filt = exprs[0]
    for e in exprs[1:]:
        filt = filt & e
    matched = df.filter(filt).select("row_number")
    if matched.is_empty():
        return []
    return [int(x) for x in matched.get_column("row_number").to_list()[:limit]]


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
        初始化导入导出服务。

        Args:
            db: 数据库对象（会原样传递给 handler）
            redis_client: Redis 客户端（可选，用于加锁）
            config: 导入导出配置（可选）
            base_dir: 工作目录根路径（可选，会覆盖 config.base_dir）
            max_upload_mb: 最大上传文件大小（MB，默认 20）
            lock_ttl_seconds: Redis 锁 TTL（秒，默认 300）
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
            ExportResult: 包含 path/filename/media_type 的导出结果

        Raises:
            RuntimeError: Workbook.active 为 None（XLSX 导出时）

        Examples:
            >>> async def df_fn(_db):
            ...     import polars as pl
            ...     return pl.DataFrame([{"a": 1}])
            >>> # await svc.export_table(fmt="csv", filename_prefix="items", df_fn=df_fn)
        """
        df = await df_fn(self.db)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{ts}.{fmt}"
        file_path = create_export_path(filename, config=self.config)

        if fmt == "csv":
            df.write_csv(file_path, include_bom=True, line_terminator="\r\n")
            return ExportResult(path=file_path, filename=filename, media_type="text/csv; charset=utf-8")

        wb = Workbook()
        ws = wb.active
        if ws is None:
            raise RuntimeError("Workbook.active is None")
        ws = cast(Worksheet, ws)
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
            ExportResult: 包含 path/filename/media_type 的导出结果
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        validate_fn: ValidateFn,
        allow_overwrite: bool = False,
        unique_fields: list[str] | None = None,
        db_checks: list[DbCheckSpec] | None = None,
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

        Returns:
            ImportValidateResponse: 校验响应

        Raises:
            ImportExportError: 上传文件过大时抛出
        """
        import_id = new_import_id()
        paths = get_import_paths(import_id, config=self.config)
        try:
            paths.root.mkdir(parents=True, exist_ok=True)

            filename = file.filename or "upload"
            content_type = file.content_type
            ext = Path(filename).suffix.lower()
            original_path = paths.original.with_suffix(ext)

            size = 0
            with original_path.open("wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > int(self.max_upload_mb) * 1024 * 1024:
                        raise ImportExportError(message="上传文件过大")
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

            parsed = parse_tabular_file(original_path, filename=filename)
            df = normalize_columns(parsed.df, column_aliases)
            df.write_parquet(paths.parsed_parquet)

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
            ImportPreviewResponse: 预览响应（包含 rows）

        Raises:
            ImportExportError: page/page_size/kind 参数非法或 checksum 不匹配时抛出
        """
        paths = get_import_paths(import_id, config=self.config)
        if page < 1:
            raise ImportExportError(message="page 必须 >= 1")
        if page_size < 1 or page_size > 500:
            raise ImportExportError(message="page_size 必须在 1..500 之间")
        if kind not in {"all", "valid"}:
            raise ImportExportError(message="kind 必须为 all 或 valid")
        meta = read_meta(paths)
        if str(meta.get("checksum")) != checksum:
            raise ImportExportError(message="checksum 不匹配")

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
        persist_fn: PersistFn,
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

        Args:
            body: Commit request.
                提交请求体。
            persist_fn: Domain persistence handler.
                业务落库 handler。
            lock_namespace: Namespace prefix for lock key.
                锁 key 的命名空间前缀。

        Returns:
            ImportCommitResponse: 提交响应（包含 imported_rows）

        Raises:
            ImportExportError: checksum 为空/不匹配、import_id 不存在、状态非法、存在校验错误、锁获取失败或数据库完整性错误时抛出
        """
        paths = get_import_paths(body.import_id, config=self.config)
        if not str(body.checksum).strip():
            raise ImportExportError(message="checksum 不能为空")
        if not paths.meta.exists():
            raise ImportExportError(message="import_id 不存在或已过期")
        meta = read_meta(paths)
        if str(meta.get("checksum")) != body.checksum:
            raise ImportExportError(message="checksum 不匹配")
        if str(meta.get("status")) not in {"validated", "committed"}:
            raise ImportExportError(message="导入状态非法，请先完成上传校验")

        if meta.get("status") == "committed":
            committed_at = int(meta.get("committed_at") or now_ts())
            return ImportCommitResponse(
                import_id=body.import_id,
                checksum=body.checksum,
                status="committed",
                imported_rows=int(meta.get("imported_rows") or 0),
                created_at=datetime.fromtimestamp(committed_at),
            )

        if paths.errors_json.exists():
            errors = json.loads(paths.errors_json.read_text(encoding="utf-8"))
            if errors:
                raise ImportExportError(message="存在校验错误，整批不可导入", details=errors[:200])

        lock_key = f"{lock_namespace}:lock:{body.import_id}"
        lock_acquired = False
        if self.redis_client is not None:
            result = await _maybe_await(self.redis_client.set(lock_key, "1", ex=self.lock_ttl_seconds, nx=True))
            lock_acquired = bool(result)
            if not lock_acquired:
                raise ImportExportError(message="导入正在执行，请稍后重试")

        valid_df = pl.read_parquet(paths.valid_parquet) if paths.valid_parquet.exists() else pl.DataFrame()
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
                created_at=datetime.fromtimestamp(int(meta.get("committed_at") or now_ts())),
            )
        except Exception as exc:
            meta["status"] = "commit_failed"
            meta["commit_failed_at"] = now_ts()
            meta["commit_error"] = str(exc)
            write_meta(paths, meta)

            if IntegrityError is not None and isinstance(exc, IntegrityError):
                msg, details = _format_integrity_error(exc)
                detail_text = ""
                orig = getattr(exc, "orig", None)
                if orig is not None:
                    detail_text = str(getattr(orig, "detail", "") or "")
                parsed = _parse_pg_unique_detail(detail_text) or _parse_pg_unique_detail(str(exc))
                if parsed and "columns" in parsed and "values" in parsed:
                    row_numbers = _find_conflict_row_numbers(
                        valid_df, columns=parsed["columns"], values=parsed["values"]
                    )
                    payload = {"columns": parsed["columns"], "values": parsed["values"], "row_numbers": row_numbers}
                    if details:
                        payload.update(details)
                    raise ImportExportError(
                        message=f"唯一约束冲突：{', '.join(f'{c}={v}' for c, v in zip(parsed['columns'], parsed['values'], strict=False))} 已存在（可能包含软删除记录）。",
                        details=payload,
                    ) from exc
                raise ImportExportError(message=msg, details=details) from exc

            text = str(exc)
            if "duplicate key value violates unique constraint" in text:
                parsed = _parse_pg_unique_detail(text)
                if parsed and "columns" in parsed and "values" in parsed:
                    row_numbers = _find_conflict_row_numbers(
                        valid_df, columns=parsed["columns"], values=parsed["values"]
                    )
                    return_details = {
                        "columns": parsed["columns"],
                        "values": parsed["values"],
                        "row_numbers": row_numbers,
                    }
                    raise ImportExportError(
                        message=f"唯一约束冲突：{', '.join(f'{c}={v}' for c, v in zip(parsed['columns'], parsed['values'], strict=False))} 已存在（可能包含软删除记录）。",
                        details=return_details,
                    ) from exc
                raise ImportExportError(
                    message="唯一约束冲突：导入数据与现有数据存在重复键（可能包含软删除记录）。",
                    details={"error": text},
                ) from exc
            raise
        finally:
            if self.redis_client is not None and lock_acquired:
                try:
                    await _maybe_await(self.redis_client.delete(lock_key))
                except Exception:
                    pass
