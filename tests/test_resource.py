"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_resource.py
@DateTime: 2026-02-08
@Docs: Tests for resource.py module.
resource.py 模块测试。
"""

from fastapi_import_export.resource import Resource


class TestResource:
    """Tests for Resource base class.
    Resource 基类测试。
    """

    def test_field_mapping_reverses_aliases(self) -> None:
        """field_mapping() reverses field_aliases / field_mapping() 正确反转 field_aliases。"""

        class UserResource(Resource):
            username: str
            email: str
            field_aliases = {"Username": "username", "Email": "email"}

        mapping = UserResource.field_mapping()
        assert mapping == {"Username": "username", "Email": "email"}

    def test_field_mapping_empty_when_no_aliases(self) -> None:
        """field_mapping() returns empty dict when no aliases / 无 field_aliases 时返回空字典。"""

        class EmptyResource(Resource):
            name: str

        assert EmptyResource.field_mapping() == {}

    def test_pydantic_model_dump(self) -> None:
        """Resource subclass can model_dump / Resource 子类可正常 model_dump。"""

        class ItemResource(Resource):
            id: int | None = None
            name: str

        item = ItemResource(name="test")
        dump = item.model_dump()
        assert dump["name"] == "test"
        assert dump["id"] is None

    def test_field_mapping_with_multiple_aliases(self) -> None:
        """field_mapping works with multiple aliases / 多个别名时映射正确。"""

        class BigResource(Resource):
            a: str
            b: str
            c: str
            field_aliases = {"X": "a", "Y": "b", "Z": "c"}

        mapping = BigResource.field_mapping()
        assert len(mapping) == 3
        assert mapping["X"] == "a"
        assert mapping["Y"] == "b"
        assert mapping["Z"] == "c"
