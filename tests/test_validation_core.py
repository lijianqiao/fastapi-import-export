"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_validation_core.py
@DateTime: 2026-02-08
@Docs: Tests for validation_core.py module.
validation_core.py 模块测试。
"""

from fastapi_import_export.validation_core import ErrorCollector, RowContext


class TestErrorCollector:
    """Tests for ErrorCollector.
    ErrorCollector 测试。
    """

    def test_add_required_fields(self) -> None:
        """Required fields are written / 必选字段被写入。"""
        errors: list[dict] = []
        ec = ErrorCollector(errors=errors)
        ec.add(row_number=1, field="name", message="required")
        assert len(errors) == 1
        assert errors[0]["row_number"] == 1
        assert errors[0]["field"] == "name"
        assert errors[0]["message"] == "required"

    def test_add_optional_fields_omitted_when_none(self) -> None:
        """Optional fields not written when None / 可选字段为 None 时不写入。"""
        errors: list[dict] = []
        ec = ErrorCollector(errors=errors)
        ec.add(row_number=1, field="x", message="err")
        assert "value" not in errors[0]
        assert "type" not in errors[0]
        assert "details" not in errors[0]

    def test_add_optional_fields_included_when_provided(self) -> None:
        """Optional fields included when provided / 提供可选字段时写入。"""
        errors: list[dict] = []
        ec = ErrorCollector(errors=errors)
        ec.add(row_number=2, field="ip", message="bad", value="999", type="format", details={"hint": "use IPv4"})
        assert errors[0]["value"] == "999"
        assert errors[0]["type"] == "format"
        assert errors[0]["details"] == {"hint": "use IPv4"}


class TestRowContext:
    """Tests for RowContext.
    RowContext 测试。
    """

    def test_add_delegates_to_collector(self) -> None:
        """add() delegates to collector with correct row_number / add() 正确代理并传递 row_number。"""
        errors: list[dict] = []
        ec = ErrorCollector(errors=errors)
        ctx = RowContext(collector=ec, row_number=5, row={"name": "alice"})
        ctx.add(field="name", message="too short")
        assert errors[0]["row_number"] == 5
        assert errors[0]["field"] == "name"

    def test_get_str_none_returns_empty(self) -> None:
        """get_str returns empty string for None / None 时返回空字符串。"""
        ctx = RowContext(collector=ErrorCollector(errors=[]), row_number=1, row={"a": None})
        assert ctx.get_str("a") == ""

    def test_get_str_missing_key_returns_empty(self) -> None:
        """get_str returns empty string for missing key / 键不存在时返回空字符串。"""
        ctx = RowContext(collector=ErrorCollector(errors=[]), row_number=1, row={})
        assert ctx.get_str("nonexistent") == ""

    def test_get_str_number_to_string(self) -> None:
        """get_str converts number to string / 数字转为字符串。"""
        ctx = RowContext(collector=ErrorCollector(errors=[]), row_number=1, row={"age": 25})
        assert ctx.get_str("age") == "25"

    def test_get_str_strips_whitespace(self) -> None:
        """get_str strips surrounding whitespace / 去除前后空格。"""
        ctx = RowContext(collector=ErrorCollector(errors=[]), row_number=1, row={"name": "  alice  "})
        assert ctx.get_str("name") == "alice"
