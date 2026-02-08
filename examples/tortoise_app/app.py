"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: app.py
@DateTime: 2026-02-08
@Docs: FastAPI app with import/export endpoints using Tortoise ORM.
使用 Tortoise ORM 的 FastAPI 导入导出端点示例。
"""

from typing import Any
from uuid import UUID

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from fastapi_import_export.exceptions import ImportExportError
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import ImportExportService

from .handlers import DeviceResource, df_fn, persist_fn, validate_fn


def create_app(base_dir: str | None = None) -> FastAPI:
    """Create the Tortoise ORM example app.
    创建 Tortoise ORM 示例应用。

    Args:
        base_dir: Override base_dir for ImportExportService / 覆盖 base_dir。

    Returns:
        FastAPI app instance / FastAPI 应用实例。
    """
    app = FastAPI(title="Tortoise ORM E2E Example")

    @app.exception_handler(ImportExportError)
    async def _import_export_error_handler(request: Any, exc: ImportExportError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.message, "error_code": exc.error_code, "details": exc.details},
        )

    @app.post("/import/upload")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        svc = ImportExportService(db=None, base_dir=base_dir)
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
        svc = ImportExportService(db=None, base_dir=base_dir)
        resp = await svc.preview(
            import_id=import_id, checksum=checksum, page=page, page_size=page_size, kind=kind,
        )
        return resp.model_dump(mode="json")

    @app.post("/import/{import_id}/commit")
    async def commit(import_id: UUID, checksum: str = Query(...)) -> Any:
        try:
            svc = ImportExportService(db=None, base_dir=base_dir)
            body = ImportCommitRequest(import_id=import_id, checksum=checksum)
            resp = await svc.commit(body=body, persist_fn=persist_fn)
            return resp.model_dump(mode="json")
        except Exception as exc:
            text = str(exc).lower()
            if "unique constraint" in text or "integrity" in text:
                return JSONResponse(
                    status_code=409,
                    content={"message": f"Unique constraint conflict / 唯一约束冲突: {exc}"},
                )
            raise

    @app.get("/export")
    async def export_devices() -> FileResponse:
        svc = ImportExportService(db=None, base_dir=base_dir)
        result = await svc.export_table(fmt="csv", filename_prefix="devices", df_fn=df_fn)
        return FileResponse(path=result.path, filename=result.filename, media_type=result.media_type)

    return app
