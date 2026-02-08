"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_config.py
@DateTime: 2026-02-08
@Docs: Tests for config.py module.
config.py 模块测试。
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi_import_export.config import (
    DEFAULT_ALLOWED_EXTENSIONS,
    ImportExportConfig,
    _env_get,
    _normalize_extensions,
    _normalize_mime_types,
    _split_csv,
    resolve_config,
)


class TestEnvGet:
    """Tests for _env_get helper.
    _env_get 辅助函数测试。
    """

    def test_returns_first_nonempty(self) -> None:
        """Return first non-empty env var / 返回第一个非空环境变量。"""
        with patch.dict(os.environ, {"A": "", "B": "hello"}):
            assert _env_get("A", "B") == "hello"

    def test_returns_none_when_all_empty(self) -> None:
        """Return None when all candidates are empty / 所有候选为空时返回 None。"""
        with patch.dict(os.environ, {}, clear=True):
            assert _env_get("NONEXISTENT_1", "NONEXISTENT_2") is None

    def test_strips_whitespace(self) -> None:
        """Strip surrounding whitespace / 去除前后空格。"""
        with patch.dict(os.environ, {"X": "  val  "}):
            assert _env_get("X") == "val"

    def test_skip_whitespace_only(self) -> None:
        """Skip env var with only whitespace / 跳过仅含空格的环境变量。"""
        with patch.dict(os.environ, {"A": "   ", "B": "ok"}):
            assert _env_get("A", "B") == "ok"


class TestSplitCsv:
    """Tests for _split_csv helper.
    _split_csv 辅助函数测试。
    """

    def test_none_returns_empty(self) -> None:
        assert _split_csv(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert _split_csv("") == []

    def test_normal_split(self) -> None:
        assert _split_csv(".csv, .xlsx, .xls") == [".csv", ".xlsx", ".xls"]

    def test_whitespace_items_filtered(self) -> None:
        assert _split_csv(",,,a,,b,") == ["a", "b"]


class TestNormalizeExtensions:
    """Tests for _normalize_extensions.
    _normalize_extensions 测试。
    """

    def test_adds_dot_prefix(self) -> None:
        """Add dot prefix if missing / 缺少点号前缀时自动补全。"""
        result = _normalize_extensions(["csv", "xlsx"])
        assert ".csv" in result
        assert ".xlsx" in result

    def test_lowercases(self) -> None:
        """Lowercase all extensions / 所有扩展名转小写。"""
        result = _normalize_extensions([".CSV", ".Xlsx"])
        assert all(v == v.lower() for v in result)

    def test_deduplicates_and_sorts(self) -> None:
        """Deduplicate and sort / 去重并排序。"""
        result = _normalize_extensions([".csv", ".csv", ".xlsx", ".csv"])
        assert result == (".csv", ".xlsx")

    def test_empty_items_filtered(self) -> None:
        """Filter empty items / 过滤空项。"""
        result = _normalize_extensions(["", " ", ".csv"])
        assert result == (".csv",)


class TestNormalizeMimeTypes:
    """Tests for _normalize_mime_types.
    _normalize_mime_types 测试。
    """

    def test_lowercases_and_deduplicates(self) -> None:
        result = _normalize_mime_types(["Text/CSV", "text/csv", "APPLICATION/JSON"])
        assert "text/csv" in result
        assert "application/json" in result
        assert len(set(result)) == len(result)


class TestImportExportConfig:
    """Tests for ImportExportConfig dataclass.
    ImportExportConfig 数据类测试。
    """

    def test_imports_dir(self, tmp_path: Path) -> None:
        cfg = ImportExportConfig(base_dir=tmp_path)
        assert cfg.imports_dir == tmp_path / "imports"

    def test_exports_dir(self, tmp_path: Path) -> None:
        cfg = ImportExportConfig(base_dir=tmp_path)
        assert cfg.exports_dir == tmp_path / "exports"

    def test_custom_dirname(self, tmp_path: Path) -> None:
        cfg = ImportExportConfig(base_dir=tmp_path, imports_dirname="in", exports_dirname="out")
        assert cfg.imports_dir == tmp_path / "in"
        assert cfg.exports_dir == tmp_path / "out"


class TestResolveConfig:
    """Tests for resolve_config.
    resolve_config 测试。
    """

    def test_default_base_dir(self) -> None:
        """Default base_dir is tempdir/import_export / 默认 base_dir 为临时目录/import_export。"""
        with patch.dict(os.environ, {}, clear=True):
            cfg = resolve_config()
            assert cfg.base_dir == Path(tempfile.gettempdir()) / "import_export"

    def test_base_dir_param_overrides(self, tmp_path: Path) -> None:
        """Parameter base_dir overrides env and default / 参数 base_dir 覆盖环境变量和默认值。"""
        cfg = resolve_config(base_dir=tmp_path / "custom")
        assert cfg.base_dir == tmp_path / "custom"

    def test_env_base_dir_priority(self, tmp_path: Path) -> None:
        """Env IMPORT_EXPORT_BASE_DIR takes priority over TMP_DIR / BASE_DIR 优先于 TMP_DIR。"""
        with patch.dict(
            os.environ,
            {
                "IMPORT_EXPORT_BASE_DIR": str(tmp_path / "base"),
                "IMPORT_EXPORT_TMP_DIR": str(tmp_path / "tmp"),
            },
        ):
            cfg = resolve_config()
            assert cfg.base_dir == tmp_path / "base"

    def test_env_tmp_dir_fallback(self, tmp_path: Path) -> None:
        """Env IMPORT_EXPORT_TMP_DIR as fallback / TMP_DIR 作为回退。"""
        env = {"IMPORT_EXPORT_TMP_DIR": str(tmp_path / "tmp")}
        with patch.dict(os.environ, env, clear=True):
            cfg = resolve_config()
            assert cfg.base_dir == tmp_path / "tmp"

    def test_env_allowed_extensions(self) -> None:
        """Parse allowed extensions from env / 从环境变量解析允许的扩展名。"""
        with patch.dict(os.environ, {"IMPORT_EXPORT_ALLOWED_EXTENSIONS": ".csv,.xlsx"}, clear=True):
            cfg = resolve_config()
            assert ".csv" in cfg.allowed_extensions
            assert ".xlsx" in cfg.allowed_extensions

    def test_env_allowed_mime_types(self) -> None:
        """Parse allowed MIME types from env / 从环境变量解析允许的 MIME 类型。"""
        with patch.dict(os.environ, {"IMPORT_EXPORT_ALLOWED_MIME_TYPES": "text/csv,application/json"}, clear=True):
            cfg = resolve_config()
            assert "text/csv" in cfg.allowed_mime_types

    def test_default_allowed_extensions(self) -> None:
        """Default allowed extensions applied / 使用默认允许扩展名。"""
        with patch.dict(os.environ, {}, clear=True):
            cfg = resolve_config()
            for ext in DEFAULT_ALLOWED_EXTENSIONS:
                assert ext in cfg.allowed_extensions

    def test_param_extensions_override_env(self) -> None:
        """Parameter overrides env for extensions / 参数覆盖环境变量。"""
        with patch.dict(os.environ, {"IMPORT_EXPORT_ALLOWED_EXTENSIONS": ".csv"}, clear=True):
            cfg = resolve_config(allowed_extensions=[".json"])
            assert ".json" in cfg.allowed_extensions
            assert ".csv" not in cfg.allowed_extensions
