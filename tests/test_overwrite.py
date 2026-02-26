"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_overwrite.py
@DateTime: 2026-02-26
@Docs: Tests for overwrite mode resolution.
覆盖策略解析测试。
"""

import pytest

from fastapi_import_export.overwrite import OverwriteMode, resolve_overwrite_mode


def test_default_false_maps_reject() -> None:
    allow_overwrite, mode = resolve_overwrite_mode()
    assert allow_overwrite is False
    assert mode == OverwriteMode.REJECT


def test_default_true_maps_upsert() -> None:
    allow_overwrite, mode = resolve_overwrite_mode(allow_overwrite=True)
    assert allow_overwrite is True
    assert mode == OverwriteMode.UPSERT


def test_explicit_replace_mode() -> None:
    allow_overwrite, mode = resolve_overwrite_mode(overwrite_mode="replace")
    assert allow_overwrite is True
    assert mode == OverwriteMode.REPLACE


def test_invalid_mode_raises() -> None:
    with pytest.raises(ValueError):
        resolve_overwrite_mode(overwrite_mode="unknown")
