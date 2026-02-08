"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: storage_fs.py
@DateTime: 2026-02-08
@Docs: Filesystem storage implementation.
文件系统存储实现。
"""

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import uuid6

from fastapi_import_export.config import ImportExportConfig, resolve_config


@dataclass(frozen=True, slots=True)
class ImportPaths:
    """
    Resolved paths for a single import job.
    导入任务的文件系统路径。

    Attributes:
        root: Root directory for this import job.
        root: 本次导入任务的根目录。
        original: Path prefix for uploaded original file (suffix appended later).
        original: 原始上传文件路径前缀（后续会加上扩展名）。
        meta: Path to meta.json.
        meta: meta.json 路径。
        parsed_parquet: Parsed full dataset parquet path.
        parsed_parquet: 解析后的全量数据 parquet 路径。
        errors_json: Validation errors json path.
        errors_json: 校验错误 errors.json 路径。
        valid_parquet: Valid rows parquet path.
        valid_parquet: 通过校验的有效行 parquet 路径。
    """

    root: Path
    original: Path
    meta: Path
    parsed_parquet: Path
    errors_json: Path
    valid_parquet: Path


def new_import_id() -> UUID:
    """
    Create a new import job id.
    创建新的导入任务 ID。

    Returns:
        UUID: Generated UUIDv7.
        UUID: 生成的 UUIDv7。
    """
    return uuid6.uuid7()


def now_ts() -> int:
    """
    Return current unix timestamp in seconds.
    返回当前 Unix 时间戳（秒）。

    Returns:
        int: Current timestamp in seconds.
        int: 当前时间戳（秒）。
    """
    return int(time.time())


def ensure_dirs(*, config: ImportExportConfig) -> None:
    """
    Ensure imports/exports directories exist.
    确保 imports/exports 目录存在。

    Args:
        config: ImportExportConfig instance.
        config: 导入导出配置。
    """
    config.imports_dir.mkdir(parents=True, exist_ok=True)
    config.exports_dir.mkdir(parents=True, exist_ok=True)


def get_import_paths(
    import_id: UUID, *, config: ImportExportConfig | None = None, base_dir: str | os.PathLike[str] | None = None
) -> ImportPaths:
    """
    Resolve all filesystem paths for a given import_id.
    为给定的导入任务 ID 解析所有文件系统路径。

    Args:
        import_id: Import job identifier.
        import_id: 导入任务 ID。
        config: Optional pre-resolved config.
        config: 可选：已解析好的配置。
        base_dir: Optional base directory override when config is not provided.
        base_dir: 可选：base_dir 覆盖（当 config 未提供时使用）。

    Returns:
        ImportPaths: Resolved paths.
        ImportPaths: 导入路径集合。
    """
    cfg = config or resolve_config(base_dir=base_dir)
    root = cfg.imports_dir / str(import_id)
    return ImportPaths(
        root=root,
        original=root / "original",
        meta=root / "meta.json",
        parsed_parquet=root / "parsed.parquet",
        errors_json=root / "errors.json",
        valid_parquet=root / "valid.parquet",
    )


def write_meta(paths: ImportPaths, meta: dict[str, Any]) -> None:
    """
    Write meta.json for an import job.
    为导入任务写入 meta.json。

    Args:
        paths: ImportPaths.
        paths: 导入路径集合。
        meta: JSON-serializable metadata dict.
        meta: 可 JSON 序列化的元信息字典。
    """
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_meta(paths: ImportPaths) -> dict[str, Any]:
    """
    Read meta.json for an import job.
    读取导入任务的 meta.json。

    Args:
        paths: ImportPaths.
        paths: 导入路径集合。

    Returns:
        dict[str, Any]: Parsed metadata dict.
        dict[str, Any]: 解析后的元信息字典。
    """
    return json.loads(paths.meta.read_text(encoding="utf-8"))


def sha256_file(file_path: Path) -> str:
    """
    Compute sha256 checksum of a file.
    计算文件的 sha256 校验和。

    Args:
        file_path: Path to the file.
        file_path: 文件路径。

    Returns:
        str: Hex string sha256 digest.
        str: sha256 十六进制摘要字符串。
    """
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_unlink(path: Path) -> None:
    """
    Best-effort unlink (ignore errors).
    尽力删除文件（忽略错误）。

    Args:
        path: File path.
        path: 文件路径。
    """
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def safe_rmtree(path: Path) -> None:
    """
    Best-effort recursive delete for a directory (ignore errors).
    尽力递归删除目录（忽略错误）。

    Args:
        path: Directory path.
        path: 目录路径。
    """
    shutil.rmtree(path, ignore_errors=True)


def delete_export_file(path: str) -> None:
    """
    Helper for FastAPI BackgroundTask to delete an exported file.
    为 FastAPI BackgroundTask 提供的辅助函数，用于删除导出文件。

    Args:
        path: File path string.
        path: 文件路径字符串。
    """
    safe_unlink(Path(path))


def create_export_path(
    filename: str,
    *,
    config: ImportExportConfig | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """
    Create a safe path for an export file under exports directory.
    创建 exports 目录下的安全导出文件路径。

    Args:
        filename: Desired filename (will be sanitized).
        filename: 期望的文件名（会做简单清理，避免路径穿越）。
        config: Optional config override.
        config: 可选：配置覆盖。
        base_dir: Optional base_dir override when config is not provided.
        base_dir: 可选：base_dir 覆盖（当 config 未提供时使用）。

    Returns:
        Path: Path under exports directory.
        Path: exports 目录下的安全路径。
    """
    cfg = config or resolve_config(base_dir=base_dir)
    ensure_dirs(config=cfg)
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return cfg.exports_dir / safe_name


def cleanup_expired_imports(
    *,
    ttl_hours: int,
    config: ImportExportConfig | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> int:
    """
    Cleanup expired import job directories.
    清理过期的导入任务目录。

    The function uses `meta.json.created_at` as the primary signal.
    函数使用 `meta.json.created_at` 作为主要信号。

    Args:
        ttl_hours: TTL in hours.
        ttl_hours: 过期时间（小时）。
        config: Optional config override.
        config: 可选：配置覆盖。
        base_dir: Optional base_dir override when config is not provided.
        base_dir: 可选：base_dir 覆盖（当 config 未提供时使用）。

    Returns:
        int: Number of directories cleaned.
        int: 清理的目录数量。
    """
    cfg = config or resolve_config(base_dir=base_dir)
    imports_dir = cfg.imports_dir
    if not imports_dir.exists():
        return 0
    cutoff = now_ts() - int(ttl_hours) * 3600
    cleaned = 0
    for item in imports_dir.iterdir():
        if not item.is_dir():
            continue
        meta_path = item / "meta.json"
        created_at = 0
        try:
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                created_at = int(meta.get("created_at") or 0)
        except Exception:
            created_at = 0
        try:
            if created_at and created_at >= cutoff:
                continue
            safe_rmtree(item)
            cleaned += 1
        except Exception:
            continue
    return cleaned
