"""Configuration helpers for import/export.
FastAPI 导入导出配置助手.

This module defines the directory layout used by the import/export workflow.
It is designed to be reusable across FastAPI projects and can be configured
via environment variables or function parameters.

本模块定义导入导出流程的目录布局，面向 FastAPI 项目复用。
支持通过环境变量或函数参数进行配置。

Environment variables / 环境变量:
    - IMPORT_EXPORT_BASE_DIR / IMPORT_EXPORT_TMP_DIR:
      Base directory for the whole import/export workspace.
      导入导出工作目录根路径。
    - IMPORT_EXPORT_IMPORTS_DIRNAME:
      Subdirectory name for imports (default: imports).
      imports 子目录名称（默认 imports）。
    - IMPORT_EXPORT_EXPORTS_DIRNAME:
      Subdirectory name for exports (default: exports).
      exports 子目录名称（默认 exports）。

Examples:
    Use default temp directory / 使用默认临时目录:

    >>> from fastapi_import_export.config import resolve_config
    >>> cfg = resolve_config()
    >>> cfg.imports_dir.name
    'imports'

    Custom base_dir / 自定义 base_dir:

    >>> cfg = resolve_config(base_dir="D:/tmp/import-export")
    >>> str(cfg.base_dir).endswith("import-export")
    True
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ImportExportConfig:
    """Import/export workspace configuration.

    导入导出工作区配置.

    Attributes:
        base_dir: Base directory of the workspace.
            工作区根目录。
        imports_dirname: Imports subdirectory name.
            imports 子目录名称。
        exports_dirname: Exports subdirectory name.
            exports 子目录名称。
    """

    base_dir: Path
    imports_dirname: str = "imports"
    exports_dirname: str = "exports"

    @property
    def imports_dir(self) -> Path:
        """Return the imports directory.

        返回 imports 目录路径。

        Returns:
            Imports directory path.
                imports 目录路径。
        """
        return self.base_dir / self.imports_dirname

    @property
    def exports_dir(self) -> Path:
        """Return the exports directory.

        返回 exports 目录路径。

        Returns:
            Exports directory path.
                exports 目录路径。
        """
        return self.base_dir / self.exports_dirname


def _env_get(*names: str) -> str | None:
    """Get the first non-empty environment variable value.

    获取第一个非空环境变量值。

    Args:
        *names: Candidate environment variable names in priority order.
            候选环境变量名（按优先级顺序）。

    Returns:
        The first non-empty value, or None.
            返回第一个非空值；若都为空则返回 None。
    """
    for n in names:
        v = os.getenv(n)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def resolve_config(
    *,
    base_dir: str | os.PathLike[str] | None = None,
    imports_dirname: str = "imports",
    exports_dirname: str = "exports",
    env_prefix: str = "IMPORT_EXPORT",
) -> ImportExportConfig:
    """Resolve configuration from parameters and environment variables.

    从参数和环境变量解析配置。

    Resolution order / 解析优先级:
        1) `base_dir` parameter / 函数参数 base_dir
        2) env: `{env_prefix}_BASE_DIR` or `{env_prefix}_TMP_DIR`
           环境变量：`{env_prefix}_BASE_DIR` 或 `{env_prefix}_TMP_DIR`
        3) system temp directory: `<temp>/import_export`
           系统临时目录：`<temp>/import_export`

    Args:
        base_dir: Base directory for the workspace.
            工作区根目录。
        imports_dirname: Imports subdirectory name.
            imports 子目录名称。
        exports_dirname: Exports subdirectory name.
            exports 子目录名称。
        env_prefix: Prefix for environment variables.
            环境变量前缀（默认 IMPORT_EXPORT）。

    Returns:
        An ImportExportConfig instance.
            返回 ImportExportConfig 配置实例。

    Examples:
        >>> cfg = resolve_config(env_prefix="IMPORT_EXPORT")
        >>> isinstance(cfg.base_dir, Path)
        True
    """
    env_base_dir = _env_get(f"{env_prefix}_BASE_DIR", f"{env_prefix}_TMP_DIR", "FASTAPI_IMPORT_EXPORT_BASE_DIR")
    resolved_base = Path(base_dir) if base_dir is not None else (Path(env_base_dir) if env_base_dir else None)

    if resolved_base is None:
        resolved_base = Path(tempfile.gettempdir()) / "import_export"

    env_imports = _env_get(f"{env_prefix}_IMPORTS_DIRNAME")
    env_exports = _env_get(f"{env_prefix}_EXPORTS_DIRNAME")
    return ImportExportConfig(
        base_dir=resolved_base,
        imports_dirname=env_imports or imports_dirname,
        exports_dirname=env_exports or exports_dirname,
    )
