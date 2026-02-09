"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_resource.py
@DateTime: 2026-02-08
@Docs: Tests for resource.py module.
resource.py 模块测试。
"""

import pytest

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
        assert mapping["Username"] == "username"
        assert mapping["Email"] == "email"
        assert mapping["username"] == "username"
        assert mapping["email"] == "email"

    def test_field_mapping_empty_when_no_aliases(self) -> None:
        """field_mapping() returns empty dict when no aliases / 无 field_aliases 时返回空字典。"""

        class EmptyResource(Resource):
            name: str

        assert EmptyResource.field_mapping() == {"name": "name"}

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
        assert len(mapping) == 6
        assert mapping["X"] == "a"
        assert mapping["Y"] == "b"
        assert mapping["Z"] == "c"
        assert mapping["a"] == "a"
        assert mapping["b"] == "b"
        assert mapping["c"] == "c"

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

    def test_model_binding_infers_fields(self) -> None:
        """Model binding infers fields when no declarations / 未声明字段时自动推断。"""
        pytest.importorskip("sqlalchemy")
        from sqlalchemy import Column, DateTime, Integer, String
        from sqlalchemy.orm import declarative_base

        Base = declarative_base()

        class Book(Base):
            __tablename__ = "books"
            id = Column(Integer, primary_key=True, autoincrement=True)
            title = Column(String, nullable=False)
            created_at = Column(DateTime)
            deleted = Column(Integer)

        class BookResource(Resource):
            model = Book

        assert BookResource.field_order() == ["title"]
        assert BookResource.field_mapping() == {"title": "title"}

    def test_model_binding_exclude_fields(self) -> None:
        """exclude_fields removes extra fields / exclude_fields 可排除字段。"""
        pytest.importorskip("sqlalchemy")
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.orm import declarative_base

        Base = declarative_base()

        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True, autoincrement=True)
            username = Column(String, nullable=False)
            password = Column(String, nullable=False)

        class UserResource(Resource):
            model = User
            exclude_fields = ["password"]

        assert UserResource.field_order() == ["username"]

    def test_model_binding_field_aliases_override(self) -> None:
        """field_aliases overrides inferred mapping / field_aliases 覆盖自动映射。"""
        pytest.importorskip("sqlalchemy")
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.orm import declarative_base

        Base = declarative_base()

        class Author(Base):
            __tablename__ = "authors"
            id = Column(Integer, primary_key=True, autoincrement=True)
            author = Column(String, nullable=False)

        class AuthorResource(Resource):
            model = Author
            field_aliases = {"Author Name": "author"}

        assert AuthorResource.field_mapping() == {"author": "author", "Author Name": "author"}

    def test_model_binding_sqlmodel_infers_fields(self) -> None:
        """SQLModel model binding infers fields / SQLModel 自动推断字段。"""
        pytest.importorskip("sqlmodel")
        from sqlmodel import Field, SQLModel

        class Book(SQLModel, table=True):
            id: int | None = Field(default=None, primary_key=True)
            title: str
            sku: str

        class BookResource(Resource):
            model = Book

        assert BookResource.field_order() == ["title", "sku"]

    @pytest.mark.asyncio
    async def test_model_binding_tortoise_infers_fields(self) -> None:
        """Tortoise model binding infers fields / Tortoise 自动推断字段。"""
        pytest.importorskip("tortoise")

        from tortoise import Tortoise, fields, models

        class Device(models.Model):
            id = fields.IntField(primary_key=True)
            name = fields.CharField(max_length=50)
            deleted = fields.BooleanField(default=False)

        # Ensure model is discoverable by Tortoise when importing this module.
        globals()["Device"] = Device

        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": [__name__]})
        await Tortoise.generate_schemas()
        try:
            class DeviceResource(Resource):
                model = Device

            assert DeviceResource.field_order() == ["name"]
        finally:
            await Tortoise.close_connections()
