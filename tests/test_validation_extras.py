"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_validation_extras.py
@DateTime: 2026-02-08
@Docs: Tests for validation_extras.py module.
validation_extras.py 模块测试。
"""

from typing import Any

from fastapi_import_export.validation_extras import RowValidator


def _make_validator(row: dict[str, Any], row_number: int = 1) -> tuple[RowValidator, list[dict]]:
    """Helper: create a RowValidator with a fresh error list.
    辅助：创建一个带全新错误列表的 RowValidator。
    """
    errors: list[dict] = []
    rv = RowValidator(errors=errors, row_number=row_number, row=row)
    return rv, errors


class TestNotBlank:
    """Tests for not_blank.
    not_blank 测试。
    """

    def test_blank_reports_error(self) -> None:
        rv, errors = _make_validator({"name": ""})
        rv.not_blank("name", "required")
        assert len(errors) == 1
        assert errors[0]["type"] == "required"

    def test_non_blank_no_error(self) -> None:
        rv, errors = _make_validator({"name": "alice"})
        rv.not_blank("name", "required")
        assert len(errors) == 0

    def test_none_reports_error(self) -> None:
        rv, errors = _make_validator({"name": None})
        rv.not_blank("name", "required")
        assert len(errors) == 1


class TestIpAddress:
    """Tests for ip_address.
    ip_address 测试。
    """

    def test_valid_ipv4(self) -> None:
        rv, errors = _make_validator({"ip": "192.168.1.1"})
        rv.ip_address("ip", "invalid ip")
        assert len(errors) == 0

    def test_valid_ipv6(self) -> None:
        rv, errors = _make_validator({"ip": "::1"})
        rv.ip_address("ip", "invalid ip")
        assert len(errors) == 0

    def test_invalid_ip(self) -> None:
        rv, errors = _make_validator({"ip": "999.999.999.999"})
        rv.ip_address("ip", "invalid ip")
        assert len(errors) == 1
        assert errors[0]["type"] == "format"

    def test_empty_skips(self) -> None:
        rv, errors = _make_validator({"ip": ""})
        rv.ip_address("ip", "invalid ip")
        assert len(errors) == 0


class TestOneOf:
    """Tests for one_of.
    one_of 测试。
    """

    def test_allowed_value(self) -> None:
        rv, errors = _make_validator({"status": "active"})
        rv.one_of("status", {"active", "inactive"}, "invalid status")
        assert len(errors) == 0

    def test_disallowed_value(self) -> None:
        rv, errors = _make_validator({"status": "unknown"})
        rv.one_of("status", {"active", "inactive"}, "invalid status")
        assert len(errors) == 1
        assert errors[0]["type"] == "enum"

    def test_empty_skips(self) -> None:
        rv, errors = _make_validator({"status": ""})
        rv.one_of("status", {"active"}, "invalid status")
        assert len(errors) == 0


class TestRegex:
    """Tests for regex.
    regex 测试。
    """

    def test_matching(self) -> None:
        rv, errors = _make_validator({"code": "ABC123"})
        rv.regex("code", r"[A-Z]{3}\d{3}", "invalid code")
        assert len(errors) == 0

    def test_not_matching(self) -> None:
        rv, errors = _make_validator({"code": "abc"})
        rv.regex("code", r"[A-Z]{3}\d{3}", "invalid code")
        assert len(errors) == 1
        assert errors[0]["type"] == "format"

    def test_empty_skips(self) -> None:
        rv, errors = _make_validator({"code": ""})
        rv.regex("code", r"[A-Z]+", "invalid code")
        assert len(errors) == 0


class TestRequireFields:
    """Tests for require_fields.
    require_fields 测试。
    """

    def test_all_present(self) -> None:
        rv, errors = _make_validator({"a": "1", "b": "2"})
        rv.require_fields(["a", "b"], "Missing")
        assert len(errors) == 0

    def test_some_missing(self) -> None:
        rv, errors = _make_validator({"a": "1", "b": ""})
        rv.require_fields(["a", "b"], "Missing")
        assert len(errors) == 1
        assert errors[0]["field"] == "b"


class TestDbUniqueConflict:
    """Tests for db_unique_conflict.
    db_unique_conflict 测试。
    """

    def test_allow_overwrite_skips(self) -> None:
        """allow_overwrite=True skips check / allow_overwrite=True 时跳过检查。"""
        rv, errors = _make_validator({"email": "a@b.com"})
        rv.db_unique_conflict(
            field="email",
            deleted_map={"a@b.com": False},
            allow_overwrite=True,
            exists_message="exists",
            deleted_message="deleted",
        )
        assert len(errors) == 0

    def test_deleted_true_reports(self) -> None:
        rv, errors = _make_validator({"email": "a@b.com"})
        rv.db_unique_conflict(
            field="email",
            deleted_map={"a@b.com": True},
            allow_overwrite=False,
            exists_message="exists",
            deleted_message="deleted",
        )
        assert len(errors) == 1
        assert errors[0]["type"] == "db_conflict"
        assert "deleted" in errors[0]["message"].lower()

    def test_deleted_false_reports(self) -> None:
        rv, errors = _make_validator({"email": "a@b.com"})
        rv.db_unique_conflict(
            field="email",
            deleted_map={"a@b.com": False},
            allow_overwrite=False,
            exists_message="exists",
            deleted_message="deleted",
        )
        assert len(errors) == 1
        assert "db_conflict" in errors[0]["type"]

    def test_empty_value_skips(self) -> None:
        rv, errors = _make_validator({"email": ""})
        rv.db_unique_conflict(
            field="email",
            deleted_map={"a@b.com": False},
            allow_overwrite=False,
            exists_message="exists",
            deleted_message="deleted",
        )
        assert len(errors) == 0

    def test_value_not_in_map_no_error(self) -> None:
        rv, errors = _make_validator({"email": "new@b.com"})
        rv.db_unique_conflict(
            field="email",
            deleted_map={"a@b.com": False},
            allow_overwrite=False,
            exists_message="exists",
            deleted_message="deleted",
        )
        assert len(errors) == 0
