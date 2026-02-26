"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: overwrite.py
@DateTime: 2026-02-26
@Docs: Overwrite mode helpers for import commit semantics.
导入提交覆盖策略语义辅助。
"""

from enum import StrEnum


class OverwriteMode(StrEnum):
    """Overwrite behavior mode for import commit.
    导入提交时的覆盖行为模式。

    REJECT: Reject duplicates/conflicts and do not overwrite.
        遇到重复/冲突时拒绝，不覆盖。
    UPSERT: Update existing by unique key and insert new rows.
        按唯一键更新已存在数据并插入新行。
    REPLACE: Replace existing target rows in business-defined manner.
        按业务定义替换已存在目标行。
    """

    REJECT = "reject"
    UPSERT = "upsert"
    REPLACE = "replace"


def resolve_overwrite_mode(
    *,
    allow_overwrite: bool = False,
    overwrite_mode: str | OverwriteMode | None = None,
) -> tuple[bool, OverwriteMode]:
    """Resolve overwrite mode to a stable mode + bool flag.
    解析覆盖模式，返回稳定的模式与布尔标志。

    Rules:
        - If `overwrite_mode` is provided, it has higher priority.
          若提供 `overwrite_mode`，优先使用该值。
        - If not provided, `allow_overwrite=False` maps to `reject`.
          未提供时，`allow_overwrite=False` 映射为 `reject`。
        - If not provided, `allow_overwrite=True` maps to `upsert` (safe default).
          未提供时，`allow_overwrite=True` 映射为 `upsert`（安全默认）。

    Args:
        allow_overwrite: Legacy overwrite flag.
            兼容历史的覆盖布尔标志。
        overwrite_mode: Explicit overwrite mode string.
            显式覆盖模式字符串。

    Returns:
        tuple[bool, OverwriteMode]:
            - bool: Whether overwrite behavior is enabled.
              bool: 是否启用覆盖行为。
            - OverwriteMode: Resolved overwrite mode.
              OverwriteMode: 解析后的覆盖模式。

    Raises:
        ValueError: If overwrite_mode is invalid.
            overwrite_mode 无效时抛出 ValueError。
    """
    if overwrite_mode is None:
        mode = OverwriteMode.UPSERT if allow_overwrite else OverwriteMode.REJECT
    elif isinstance(overwrite_mode, OverwriteMode):
        mode = overwrite_mode
    else:
        normalized = str(overwrite_mode).strip().lower()
        try:
            mode = OverwriteMode(normalized)
        except Exception as exc:
            raise ValueError(
                "overwrite_mode must be one of reject/upsert/replace / overwrite_mode 必须为 reject/upsert/replace"
            ) from exc
    return mode != OverwriteMode.REJECT, mode
