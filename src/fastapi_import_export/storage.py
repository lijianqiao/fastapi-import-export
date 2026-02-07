"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: storage.py
@DateTime: 2026-02-08
@Docs: Storage facade with optional filesystem backend.
存储门面（可选文件系统后端）。
"""

from typing import TYPE_CHECKING, Any

from fastapi_import_export.exceptions import ImportExportError


def _load_backend() -> Any:
    try:
        from fastapi_import_export import storage_fs

        return storage_fs
    except Exception as exc:  # pragma: no cover
        raise ImportExportError(
            message="Missing optional dependencies for storage. Install extras: storage / 缺少存储可选依赖，请安装: storage",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


def new_import_id():
    """
    Create a new import job id.
    创建新的导入任务 ID。
    """
    backend = _load_backend()
    return backend.new_import_id()


def now_ts() -> int:
    """
    Return current unix timestamp in seconds.
    返回当前 Unix 时间戳（秒）。
    """
    backend = _load_backend()
    return backend.now_ts()


def ensure_dirs(*, config):
    """
    Ensure imports/exports directories exist.
    确保 imports/exports 目录存在。
    """
    backend = _load_backend()
    return backend.ensure_dirs(config=config)


def get_import_paths(import_id, *, config=None, base_dir=None):
    """
    Resolve all filesystem paths for a given import_id.
    为给定的导入任务 ID 解析所有文件系统路径。
    """
    backend = _load_backend()
    return backend.get_import_paths(import_id, config=config, base_dir=base_dir)


def write_meta(paths, meta: dict[str, Any]) -> None:
    """
    Write meta.json for an import job.
    为导入任务写入 meta.json。
    """
    backend = _load_backend()
    return backend.write_meta(paths, meta)


def read_meta(paths) -> dict[str, Any]:
    """
    Read meta.json for an import job.
    读取导入任务的 meta.json。
    """
    backend = _load_backend()
    return backend.read_meta(paths)


def sha256_file(file_path) -> str:
    """
    Compute sha256 checksum of a file.
    计算文件的 sha256 校验和。
    """
    backend = _load_backend()
    return backend.sha256_file(file_path)


def safe_unlink(path) -> None:
    """
    Best-effort unlink (ignore errors).
    尽力删除文件（忽略错误）。
    """
    backend = _load_backend()
    return backend.safe_unlink(path)


def safe_rmtree(path) -> None:
    """
    Best-effort recursive delete for a directory (ignore errors).
    尽力递归删除目录（忽略错误）。
    """
    backend = _load_backend()
    return backend.safe_rmtree(path)


def delete_export_file(path: str) -> None:
    """
    Helper for FastAPI BackgroundTask to delete an exported file.
    为 FastAPI BackgroundTask 提供的辅助函数，用于删除导出文件。
    """
    backend = _load_backend()
    return backend.delete_export_file(path)


def create_export_path(filename: str, *, config=None, base_dir=None):
    """
    Create a safe path for an export file under exports directory.
    创建 exports 目录下的安全导出文件路径。
    """
    backend = _load_backend()
    return backend.create_export_path(filename, config=config, base_dir=base_dir)


def cleanup_expired_imports(*, ttl_hours: int, config=None, base_dir=None) -> int:
    """
    Cleanup expired import job directories.
    清理过期的导入任务目录。
    """
    backend = _load_backend()
    return backend.cleanup_expired_imports(ttl_hours=ttl_hours, config=config, base_dir=base_dir)


if TYPE_CHECKING:
    from fastapi_import_export.storage_fs import ImportPaths as ImportPaths
else:

    class ImportPaths:  # noqa: D101
        """
        ImportPaths placeholder when optional backend is missing.
        可选后端缺失时的 ImportPaths 占位类型。
        """
