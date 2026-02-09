"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: storage.py
@DateTime: 2026-02-08
@Docs: Storage facade with optional filesystem backend.
存储门面（可选文件系统后端）。
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi_import_export.config import ImportExportConfig
from fastapi_import_export.exceptions import ImportExportError


def _load_backend() -> Any:
    """Load the storage backend module.
    加载存储后端模块。

    This facade function attempts to import the optional filesystem-based
    backend module and returns it. If the optional backend is unavailable
    an ImportExportError is raised.
    该门面函数尝试导入可选的基于文件系统的后端模块并返回它；若不可用则抛出 ImportExportError。

    Returns:
        Any: The backend module (e.g. ``storage_fs``).
            后端模块（例如 ``storage_fs``）。

    Raises:
        ImportExportError: When the optional storage backend cannot be imported.
            当无法导入可选存储后端时抛出 ImportExportError。
    """
    try:
        from fastapi_import_export import storage_fs

        return storage_fs
    except Exception as exc:  # pragma: no cover / 覆盖忽略
        raise ImportExportError(
            message="Missing optional dependencies for storage. Install extras: storage / 缺少存储可选依赖，请安装: storage",
            details={"error": str(exc)},
            error_code="missing_dependency",
        ) from exc


def new_import_id() -> UUID:
    """Create and return a new import job identifier.
    创建并返回新的导入任务标识（UUID）。

    The implementation delegates to the storage backend, which typically
    generates a UUIDv7 for the import job.
    实现委托给存储后端，通常会生成用于导入任务的 UUIDv7。

    Returns:
        UUID: The generated import job UUID.
            生成的导入任务 UUID。
    """
    backend = _load_backend()
    return backend.new_import_id()


def now_ts() -> int:
    """Return the current Unix timestamp in seconds.
    返回当前 Unix 时间戳（单位：秒）。

    Returns:
        int: Current Unix timestamp in seconds.
            当前 Unix 时间戳（秒）。
    """
    backend = _load_backend()
    return backend.now_ts()


def ensure_dirs(*, config: ImportExportConfig) -> None:
    """Ensure that imports/exports directories exist on disk.
    确保磁盘上存在 imports/exports 目录。

    Args:
        config: ImportExportConfig instance containing base directories.
            包含基础目录信息的 ImportExportConfig 实例。

    Returns:
        None
    """
    backend = _load_backend()
    return backend.ensure_dirs(config=config)


def get_import_paths(
    import_id: UUID,
    *,
    config: ImportExportConfig | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> Any:
    """Resolve filesystem paths for an import job.
    为导入任务解析文件系统路径。

    Args:
        import_id: The UUID of the import job.
            导入任务的 UUID。
        config: Optional ImportExportConfig to override defaults.
            可选的 ImportExportConfig，用于覆盖默认配置。
        base_dir: Optional base directory override.
            可选的 base_dir 覆盖。

    Returns:
        ImportPaths-like object provided by the backend with attributes such as
        `root`, `original`, `meta`, `parsed_parquet`, `errors_json`, etc.
            后端提供的 ImportPaths 样对象，包含 `root`、`original`、`meta`、`parsed_parquet`、`errors_json` 等属性。
    """
    backend = _load_backend()
    return backend.get_import_paths(import_id, config=config, base_dir=base_dir)


def write_meta(paths: Any, meta: dict[str, Any]) -> None:
    """Write the import job metadata to disk (meta.json).
    将导入任务的元信息写入磁盘（meta.json）。

    Args:
        paths: ImportPaths-like object with `meta` attribute/paths.
            带有 `meta` 属性/路径的 ImportPaths 样对象。
        meta: JSON-serializable metadata dict to write.
            要写入的可 JSON 序列化的元信息字典。

    Returns:
        None
    """
    backend = _load_backend()
    return backend.write_meta(paths, meta)


def read_meta(paths: Any) -> dict[str, Any]:
    """Read the import job meta.json from disk and return parsed dict.
    从磁盘读取导入任务的 meta.json 并返回解析后的字典。

    Args:
        paths: ImportPaths-like object with `meta` attribute.
            带有 `meta` 属性的 ImportPaths 样对象。

    Returns:
        dict[str, Any]: Parsed metadata dictionary.
            解析后的元信息字典。
    """
    backend = _load_backend()
    return backend.read_meta(paths)


def sha256_file(file_path: Path) -> str:
    """Compute the SHA256 checksum of a file and return hex digest.
    计算文件的 SHA256 校验和并返回十六进制摘要。

    Args:
        file_path: Path to the file.
            文件路径。

    Returns:
        str: Hexadecimal SHA256 digest string.
            十六进制 SHA256 摘要字符串。
    """
    backend = _load_backend()
    return backend.sha256_file(file_path)


def safe_unlink(path: Path) -> None:
    """Attempt to unlink a file while ignoring errors.
    尝试删除文件并忽略错误（尽力而为）。

    Args:
        path: Path to the file to remove.
            要删除的文件路径。

    Returns:
        None
    """
    backend = _load_backend()
    return backend.safe_unlink(path)


def safe_rmtree(path: Path) -> None:
    """Attempt to recursively remove a directory, ignoring errors.
    尝试递归删除目录并忽略错误（尽力而为）。

    Args:
        path: Directory path to remove.
            要删除的目录路径。

    Returns:
        None
    """
    backend = _load_backend()
    return backend.safe_rmtree(path)


def delete_export_file(path: str) -> None:
    """Helper used by FastAPI BackgroundTask to delete an exported file.
    FastAPI 后台任务用于删除导出文件的辅助函数。

    Args:
        path: String path to the export file to delete.
            要删除的导出文件路径字符串。

    Returns:
        None
    """
    backend = _load_backend()
    return backend.delete_export_file(path)


def create_export_path(
    filename: str,
    *,
    config: ImportExportConfig | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Create a safe export file path in the configured exports directory.

    在配置的 exports 目录中创建安全的导出文件路径。

    The function sanitizes `filename` to avoid path traversal and returns a
    Path inside the exports directory managed by the backend.

    该函数会清理 `filename` 以避免路径穿越，并返回位于后端管理的 exports 目录内的 Path。

    Args:
        filename: Desired output filename (sanitized).
            期望的输出文件名（会被清理以保证安全）。
        config: Optional configuration to override defaults.
            可选配置，用于覆盖默认值。
        base_dir: Optional base directory override.
            可选的 base_dir 覆盖。

    Returns:
        Path: Safe path inside the exports directory.
            exports 目录下的安全路径。
    """
    backend = _load_backend()
    return backend.create_export_path(filename, config=config, base_dir=base_dir)


def cleanup_expired_imports(
    *,
    ttl_hours: int,
    config: ImportExportConfig | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> int:
    """Cleanup import job directories older than the TTL and return count.

    清理超过 TTL 的导入任务目录并返回被清理的数量。

    Args:
        ttl_hours: Time-to-live in hours; directories older than now - ttl_hours are removed.
            TTL（小时）；比当前时间早于 ttl_hours 的目录将被删除。
        config: Optional configuration override.
            可选配置覆盖。
        base_dir: Optional base directory override.
            可选 base_dir 覆盖。

    Returns:
        int: Number of directories removed.
            被删除的目录数量。
    """
    backend = _load_backend()
    return backend.cleanup_expired_imports(ttl_hours=ttl_hours, config=config, base_dir=base_dir)


if TYPE_CHECKING:
    from fastapi_import_export.storage_fs import ImportPaths as ImportPaths
else:

    class ImportPaths:  # noqa: D101 / no docstring / 无需文档字符串
        """
        ImportPaths placeholder when optional backend is missing.
        可选后端缺失时的 ImportPaths 占位类型。
        """
