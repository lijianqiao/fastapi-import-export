"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_exceptions.py
@DateTime: 2026-02-08
@Docs: Tests for exceptions.py module.
exceptions.py 模块测试。
"""

from fastapi_import_export.exceptions import (
    ExportError,
    ImportExportError,
    ParseError,
    PersistError,
    ValidationError,
)


class TestImportExportError:
    """Tests for ImportExportError.
    ImportExportError 测试。
    """

    def test_attributes(self) -> None:
        """All attributes assigned correctly / 所有属性正确赋值。"""
        exc = ImportExportError(
            message="test error",
            status_code=422,
            details={"key": "val"},
            error_code="custom_error",
        )
        assert exc.message == "test error"
        assert exc.status_code == 422
        assert exc.details == {"key": "val"}
        assert exc.error_code == "custom_error"

    def test_defaults(self) -> None:
        """Default status_code and error_code / 默认 status_code 和 error_code。"""
        exc = ImportExportError(message="msg")
        assert exc.status_code == 400
        assert exc.error_code == "import_export_error"
        assert exc.details is None

    def test_str_returns_message(self) -> None:
        """str(exc) returns message / str(exc) 返回 message 内容。"""
        exc = ImportExportError(message="hello world")
        assert str(exc) == "hello world"

    def test_is_exception(self) -> None:
        """ImportExportError is an Exception / ImportExportError 是 Exception 子类。"""
        assert issubclass(ImportExportError, Exception)


class TestSubclasses:
    """Tests for exception subclasses.
    异常子类测试。
    """

    def test_parse_error_is_subclass(self) -> None:
        assert issubclass(ParseError, ImportExportError)

    def test_validation_error_is_subclass(self) -> None:
        assert issubclass(ValidationError, ImportExportError)

    def test_persist_error_is_subclass(self) -> None:
        assert issubclass(PersistError, ImportExportError)

    def test_export_error_is_subclass(self) -> None:
        assert issubclass(ExportError, ImportExportError)

    def test_parse_error_catchable_as_base(self) -> None:
        """ParseError can be caught as ImportExportError / ParseError 可被 ImportExportError 捕获。"""
        try:
            raise ParseError(message="parse failed")
        except ImportExportError as exc:
            assert exc.message == "parse failed"
