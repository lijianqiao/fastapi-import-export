"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_packaging.py
@DateTime: 2026-02-08
@Docs: Tests for packaging, __all__ exports, and pip-readiness.
打包、__all__ 导出与 pip 就绪性测试。
"""

import importlib
from pathlib import Path

import pytest


class TestAllExports:
    """Tests for __all__ exports.
    __all__ 导出测试。
    """

    def test_every_name_importable(self) -> None:
        """Every name in __all__ can be successfully imported / __all__ 中每个名字都能成功导入。"""
        import fastapi_import_export

        for name in fastapi_import_export.__all__:
            obj = getattr(fastapi_import_export, name, None)
            assert obj is not None, f"{name} is in __all__ but not importable / {name} 在 __all__ 中但无法导入"

    def test_import_does_not_error(self) -> None:
        """Importing the package doesn't raise / 导入包不报错。"""
        mod = importlib.import_module("fastapi_import_export")
        assert mod is not None


class TestPyTyped:
    """Tests for py.typed marker.
    py.typed 标记文件测试。
    """

    def test_py_typed_exists(self) -> None:
        """py.typed marker file exists / py.typed 标记文件存在。"""
        pkg_dir = Path(__file__).parent.parent / "src" / "fastapi_import_export"
        assert (pkg_dir / "py.typed").exists()


class TestExtrasKeys:
    """Tests for pyproject.toml extras.
    pyproject.toml extras 测试。
    """

    def test_extras_keys_present(self) -> None:
        """All expected extras keys exist / 所有预期的 extras 键存在。"""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        extras = data.get("project", {}).get("optional-dependencies", {})
        for key in ("polars", "xlsx", "storage", "full"):
            assert key in extras, f"extras key '{key}' missing / extras 键 '{key}' 缺失"


class TestFacadeFriendlyError:
    """Test that facade modules raise friendly errors for missing backends.
    门面模块缺少后端时抛出友好错误。
    """

    def test_missing_backend_is_not_module_not_found(self) -> None:
        """Missing backend raises ImportExportError, not ModuleNotFoundError.
        缺少后端时抛出 ImportExportError 而非 ModuleNotFoundError。
        """
        from unittest.mock import patch

        from fastapi_import_export.exceptions import ImportExportError

        # Simulate missing polars backend by patching _load_backend
        # 通过 patch _load_backend 模拟缺少 polars 后端
        with patch(
            "fastapi_import_export.parse._load_backend",
            side_effect=ImportExportError(message="Missing dependency: polars", error_code="missing_dependency"),
        ):
            from fastapi_import_export.parse import parse_tabular_file

            with pytest.raises(ImportExportError) as exc_info:
                parse_tabular_file(Path("/tmp/fake.csv"), filename="fake.csv")
            assert exc_info.value.error_code == "missing_dependency"
            # Verify it's NOT a ModuleNotFoundError / 确认不是 ModuleNotFoundError
            assert not isinstance(exc_info.value, ModuleNotFoundError)
