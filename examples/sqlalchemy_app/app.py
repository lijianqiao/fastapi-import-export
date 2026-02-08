"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: app.py
@DateTime: 2026-02-08
@Docs: FastAPI app with import/export endpoints using SQLAlchemy.
使用 SQLAlchemy 的 FastAPI 导入导出端点示例。
"""

from typing import Any
from uuid import UUID

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import ImportExportService

from .handlers import DeviceResource, df_fn, persist_fn, validate_fn

# ---------------------------------------------------------------------------
# Engine / session factory (overridden by tests via conftest.py)
# ---------------------------------------------------------------------------
engine = create_async_engine("sqlite+aiosqlite://", echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def create_app(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    base_dir: str | None = None,
) -> FastAPI:
    """Create a FastAPI app for the SQLAlchemy example.
    创建 SQLAlchemy 示例的 FastAPI 应用。

    Args:
        session_factory: Override session factory for testing / 测试用会话工厂覆盖。
        base_dir: Override base_dir for ImportExportService / 覆盖 base_dir。

    Returns:
        FastAPI app instance / FastAPI 应用实例。
    """
    factory = session_factory or async_session_factory
    app = FastAPI(title="SQLAlchemy E2E Example")

    @app.exception_handler(ImportExportError)
    async def _import_export_error_handler(request: Any, exc: ImportExportError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.message, "error_code": exc.error_code, "details": exc.details},
        )

    async def _get_db() -> AsyncSession:
        return factory()

    @app.post("/import/upload")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        """Upload and validate a file / 上传并校验文件。"""
        async with factory() as db:
            svc = ImportExportService(db=db, base_dir=base_dir)
            resp = await svc.upload_parse_validate(
                file=file,
                column_aliases=DeviceResource.field_mapping(),
                validate_fn=validate_fn,
                unique_fields=["name"],
            )
            return resp.model_dump(mode="json")

    @app.get("/import/{import_id}/preview")
    async def preview(
        import_id: UUID,
        checksum: str = Query(...),
        page: int = Query(1),
        page_size: int = Query(50),
        kind: str = Query("all"),
    ) -> dict[str, Any]:
        """Preview parsed rows / 预览解析行。"""
        async with factory() as db:
            svc = ImportExportService(db=db, base_dir=base_dir)
            resp = await svc.preview(
                import_id=import_id,
                checksum=checksum,
                page=page,
                page_size=page_size,
                kind=kind,
            )
            return resp.model_dump(mode="json")

    @app.post("/import/{import_id}/commit")
    async def commit(import_id: UUID, checksum: str = Query(...)) -> Any:
        """Commit import to database / 提交导入到数据库。"""
        try:
            async with factory() as db:
                svc = ImportExportService(db=db, base_dir=base_dir)
                body = ImportCommitRequest(import_id=import_id, checksum=checksum)
                resp = await svc.commit(body=body, persist_fn=persist_fn)
                return resp.model_dump(mode="json")
        except Exception as exc:
            # Catch ORM IntegrityError not matched by the duck-typing check
            # 捕获鸭子类型检查未匹配的 ORM IntegrityError
            text = str(exc).lower()
            if "unique constraint" in text or "integrity" in text:
                return JSONResponse(
                    status_code=409,
                    content={"message": f"Unique constraint conflict / 唯一约束冲突: {exc}"},
                )
            raise

    @app.get("/export")
    async def export_devices() -> FileResponse:
        """Export all devices as CSV / 导出所有设备为 CSV。"""
        async with factory() as db:
            svc = ImportExportService(db=db, base_dir=base_dir)
            result = await svc.export_table(fmt="csv", filename_prefix="devices", df_fn=df_fn)
            return FileResponse(
                path=result.path,
                filename=result.filename,
                media_type=result.media_type,
            )

    return app
