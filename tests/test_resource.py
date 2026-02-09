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

    def test_export_mapping_inverts_field_aliases(self) -> None:
        """export_mapping inverts field_aliases when reversible / export_mapping 姝ｇ‘鍙嶈浆 field_aliases銆?"""

        class UserResource(Resource):
            username: str
            email: str
            field_aliases = {"Username": "username", "Email": "email"}

        mapping = UserResource.export_mapping()
        assert mapping == {"username": "Username", "email": "Email"}

    def test_export_mapping_conflict_fallbacks_to_identity(self) -> None:
        """Conflict in field_aliases falls back to identity mapping / 冲突时回退为字段名映射"""

        class BadResource(Resource):
            username: str
            field_aliases = {"User": "username", "U": "username"}

        mapping = BadResource.export_mapping()
        assert mapping["username"] == "username"

    def test_export_mapping_export_aliases_override(self) -> None:
        """export_aliases overrides field_aliases / export_aliases 优先级更高"""

        class AliasResource(Resource):
            username: str
            export_aliases = {"username": "User Name"}
            field_aliases = {"User": "username"}

        mapping = AliasResource.export_mapping()
        assert mapping == {"username": "User Name"}
