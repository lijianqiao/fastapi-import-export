# fastapi_import_export

FastAPI 优先的导入导出工具库，保持业务模型解耦。

其他语言: [README.md](README.md) | [README_JP.md](README_JP.md)

## 主要特性

- 异步优先的导入/导出生命周期钩子。
- 显式 Resource 映射，避免 ORM 强耦合。
- 可插拔后端：解析/存储/校验按需启用。
- 导出支持流式输出，适配大数据集。

## 环境要求

- Python 3.12-3.14
- FastAPI 0.128+

## 版本兼容矩阵

| 组件     | 支持范围  | 说明                         |
| -------- | --------- | ---------------------------- |
| Python   | 3.12-3.14 | 面向异步工作流测试。         |
| FastAPI  | 0.128+    | 使用 UploadFile 与异步端点。 |
| Pydantic | 2.x       | 模型基于 BaseModel。         |
| polars   | 1.x       | 默认安装包含。               |
| openpyxl | 3.x       | 默认安装包含。               |

## 为什么不是 django-import-export

- Django 生态的 ORM/Admin 强耦合不适配 FastAPI 的异步工作流。
- 本库以异步为先，定位为工具库而非框架。
- 提供稳定、可组合的 API 与显式生命周期钩子。

## 核心边界

- 不管理数据库连接。
- 不接管 ORM，仅做适配。
- 不处理权限鉴权。
- 不处理文件存储（仅提供可插拔后端）。

## 安装

标准安装（开箱即用）：

```bash
pip install fastapi-import-export
# 或
uv add fastapi-import-export
```

默认包含 Polars/XLSX/存储辅助。ORM 适配器为可选项：

```bash
# sqlalchemy
pip install fastapi-import-export[sqlalchemy]
# sqlmodel
pip install fastapi-import-export[sqlmodel]
# tortoise
pip install fastapi-import-export[tortoise]
# 或
# sqlalchemy
uv add fastapi-import-export[sqlalchemy]
# sqlmodel
uv add fastapi-import-export[sqlmodel]
# tortoise
uv add fastapi-import-export[tortoise]
```

数据库驱动请按需自行安装（例如 `asyncpg`、`aiomysql`）。

开发与单元测试依赖：

```bash
pip install fastapi-import-export pytest pytest-asyncio pytest-cov anyio
# 或
uv add --group dev fastapi-import-export pytest pytest-asyncio pytest-cov anyio
```

E2E 集成测试依赖（可选，用于运行示例应用）：

```bash
pip install fastapi-import-export[sqlalchemy] httpx python-multipart aiosqlite
# 或
uv add --group e2e fastapi-import-export[sqlalchemy] httpx python-multipart aiosqlite
```

## 快速开始（易用层）

### 1) 定义 Resource

```python
from fastapi_import_export import Resource


class UserResource(Resource):
    id: int | None
    username: str
    email: str

    field_aliases = {
        "Username": "username",
        "Email": "email",
    }
```

### 2) 一行导入 CSV/XLSX

```python
from fastapi import APIRouter, UploadFile
from fastapi_import_export import import_csv

router = APIRouter()


async def validate_fn(db, df, *, allow_overwrite: bool = False):
    return df, []


async def persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
    return int(valid_df.height)


@router.post("/import")
async def import_data(file: UploadFile):
    return await import_csv(
        file,
        resource=UserResource,
        validate_fn=validate_fn,
        persist_fn=persist_fn,
    )
```

### 3) 导出 CSV/XLSX

```python
from fastapi import StreamingResponse
from fastapi_import_export import export_csv


async def query_fn(*, resource, params=None):
    return [
        {"id": 1, "username": "alice"},
        {"id": 2, "username": "bob"},
    ]


payload = await export_csv(query_fn, resource=UserResource)
return StreamingResponse(payload.stream, media_type=payload.media_type)
```

## ORM 适配器（可选）

ORM 适配器位于 `fastapi_import_export.contrib`，支持 SQLAlchemy/SQLModel/Tortoise。
安装方式：

```bash
pip install fastapi-import-export[sqlalchemy]
# 或
pip install fastapi-import-export[sqlmodel]
# 或
pip install fastapi-import-export[tortoise]
```

你将获得：

- ORM 模型字段自动推断（列顺序与必填判断）。
- 自动类型转换（Enum/Date/Datetime/Decimal/Bool）。
- 可通过 `field_codecs` / `__import_export_codecs__` 覆盖单字段解析规则。

## Codecs（Widget 系统）

Codecs 负责常见类型的导入/导出转换。内置支持
Enum/Date/Datetime/Decimal/Bool，可按字段注册自定义转换。
易用层会在 `validate_fn/persist_fn` 前自动应用 codecs，并在导出时格式化字段值。

```python
from enum import Enum

from fastapi_import_export import Resource
from fastapi_import_export.codecs import DateCodec, DecimalCodec, EnumCodec


class Status(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class BookResource(Resource):
    field_codecs = {
        "status": EnumCodec(Status),
        "published_at": DateCodec(),
        "price": DecimalCodec(),
    }
```

## Resource 绑定模型（轻量实现）

当 Resource 仅声明 `model` 而**未显式声明字段**时，将自动从 ORM 模型推断字段：

- 来源：`model.__table__.columns`（SQLAlchemy/SQLModel）或 `model._meta`（Tortoise）
- 自动排除：主键（`id`）、`created_at`、`updated_at`、软删除标记
- 可配置：`exclude_fields = ["password"]`
- 显式优先：`field_aliases` 永远覆盖自动映射

```python
class BookResource(Resource):
    model = Book
    exclude_fields = ["password"]
    field_aliases = {"Author": "author"}  # 覆盖自动映射
```

## 高级（Hooks）

高级 API 位于 `fastapi_import_export.advanced`，提供完整的生命周期钩子。

### 1) 定义 Resource

```python
from fastapi_import_export import Resource


class UserResource(Resource):
    id: int | None
    username: str
    email: str

    field_aliases = {
        "Username": "username",
        "Email": "email",
    }
```

### 2) 组装 Importer

```python
from fastapi_import_export.advanced import Importer


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)
```

### 3) FastAPI 接入示例

```python
from uuid import UUID

from fastapi import APIRouter, UploadFile


router = APIRouter()


@router.post("/import")
async def import_data(file: UploadFile):
    result = await importer.import_data(file=file, resource=UserResource)
    return result
```

## 异步导入示例

```python
async def validate_fn(*, data, resource, allow_overwrite=False):
    return data, []


async def persist_fn(*, data, resource, allow_overwrite=False):
    return 100
```

## 大文件导出（流式）

```python
from fastapi import StreamingResponse


payload = await exporter.stream(
    resource=UserResource,
    fmt="csv",
    filename="users.csv",
    media_type="text/csv",
)
return StreamingResponse(payload.stream, media_type=payload.media_type)
```

## Exporter 使用示例

如果 Excel 打开 CSV 乱码，建议输出 UTF-8 BOM（使用 `utf-8-sig`）。

```python
import csv
import io
from collections.abc import AsyncIterator

from fastapi_import_export.advanced import Exporter, Resource


class UserResource(Resource):
    id: int | None
    username: str


async def query_fn(*, resource: type[Resource], params: dict | None = None):
    return [
        {"id": 1, "username": "alice"},
        {"id": 2, "username": "bob"},
    ]


async def serialize_fn(*, data: list[dict], fmt: str) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id", "username"])
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8-sig")


async def render_fn(*, data: bytes, fmt: str) -> AsyncIterator[bytes]:
    async def _stream() -> AsyncIterator[bytes]:
        yield data

    return _stream()


exporter = Exporter(query_fn=query_fn, serialize_fn=serialize_fn, render_fn=render_fn)
payload = await exporter.stream(
    resource=UserResource,
    fmt="csv",
    filename="users.csv",
    media_type="text/csv",
)
```

## 可插拔后端门面

- parse/storage/validation/db_validation 为惰性加载门面。
- 只有在移除内置依赖或使用可选适配器/驱动且未安装时才会抛出 missing_dependency。

## 上传白名单配置

优先级顺序：单次调用覆盖 > resolve_config 参数 > 环境变量 > 默认值。

单次调用覆盖：

```python
await svc.upload_parse_validate(
    file=file,
    column_aliases=UserResource.field_mapping(),
    validate_fn=service_validate_fn,
    allowed_extensions=[".csv"],
    allowed_mime_types=["text/csv"],
)
```

配置层覆盖：

```python
from fastapi_import_export.config import resolve_config


cfg = resolve_config(
    allowed_extensions=[".csv", ".xlsx"],
    allowed_mime_types=["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
)
svc = ImportExportService(db=object(), config=cfg)
```

环境变量示例：

```bash
export IMPORT_EXPORT_ALLOWED_EXTENSIONS=".csv,.xlsx"
export IMPORT_EXPORT_ALLOWED_MIME_TYPES="text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

## 唯一约束冲突检测

提交导入数据时，库会自动检测数据库的唯一约束冲突并返回用户友好的错误响应。
`constraint_parser` 模块支持五种数据库的精确错误解析：

| 数据库          | 错误格式                                              | 提取信息         |
| --------------- | ----------------------------------------------------- | ---------------- |
| PostgreSQL      | `Key (col)=(val) already exists.`                     | 列名、值、约束名 |
| MySQL / MariaDB | `Duplicate entry 'val' for key 'key_name'`            | 值、约束名       |
| SQLite          | `UNIQUE constraint failed: table.col`                 | 列名             |
| SQL Server      | `Violation of UNIQUE KEY constraint 'name'`           | 值、约束名       |
| Oracle          | `ORA-00001: unique constraint (SCHEMA.NAME) violated` | 约束名           |

也可以在业务代码中直接使用解析器：

```python
from fastapi_import_export.advanced import ConstraintDetail, parse_unique_constraint_error

detail: ConstraintDetail | None = parse_unique_constraint_error(
    str(exc), detail_text=getattr(getattr(exc, "orig", None), "detail", "")
)
if detail:
    print(detail.db_type, detail.columns, detail.values)
```

## 端到端示例

下面是一个最小的端到端流程，覆盖上传、校验、预览、提交。

```python
from uuid import UUID

from fastapi import APIRouter, UploadFile

from fastapi_import_export.advanced import Importer, Resource
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.advanced import ImportExportService


class UserResource(Resource):
    id: int | None
    username: str
    email: str

    field_aliases = {
        "Username": "username",
        "Email": "email",
    }


async def parse_fn(*, file: UploadFile, resource: type[Resource]):
    return await some_parse_impl(file=file, resource=resource)


async def validate_fn(*, data, resource: type[Resource], allow_overwrite: bool = False):
    return data, []


async def transform_fn(*, data, resource: type[Resource]):
    return data


async def persist_fn(*, data, resource: type[Resource], allow_overwrite: bool = False) -> int:
    return 100


async def service_validate_fn(db, df, *, allow_overwrite: bool = False):
    return df, []


async def service_persist_fn(db, valid_df, *, allow_overwrite: bool = False) -> int:
    return 100


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)

router = APIRouter()


@router.post("/import")
async def import_data(file: UploadFile):
    return await importer.import_data(file=file, resource=UserResource)


# 可选：使用服务类进行上传/预览/提交工作流
svc = ImportExportService(db=object())


@router.post("/import/validate")
async def import_validate(file: UploadFile):
    return await svc.upload_parse_validate(
        file=file,
        column_aliases=UserResource.field_mapping(),
        validate_fn=service_validate_fn,
    )


@router.get("/import/preview")
async def import_preview(import_id: UUID, checksum: str, page: int = 1, page_size: int = 50):
    return await svc.preview(
        import_id=import_id,
        checksum=checksum,
        page=page,
        page_size=page_size,
        kind="all",
    )


@router.post("/import/commit")
async def import_commit(body: ImportCommitRequest):
    return await svc.commit(body=body, persist_fn=service_persist_fn)
```

## FAQ

**为什么会提示缺少依赖？**

你可能移除了内置依赖，或正在使用未安装的适配器/驱动（例如 ORM 适配器未安装对应 extra）。
请重新安装基础包或安装对应依赖。

**为什么校验后数据被过滤？**

服务类会将校验失败的行从 `valid.parquet` 中剔除。
如需查看原始解析数据，请使用 `kind=all` 预览。

## 常见错误排查

- **上传文件过大**：创建 `ImportExportService` 时提高 `max_upload_mb`。
- **checksum 不匹配**：确保客户端使用 `upload_parse_validate` 返回的 checksum。
- **missing_dependency**：重新安装内置依赖或安装所需适配器/驱动。
- **db_conflict**：检查唯一约束与软删除记录是否导致冲突。

## 测试

运行单元测试（依赖安装见 [安装](#安装)）：

```bash
pytest tests/ -v
```

运行 E2E 集成测试：

```bash
pytest examples/ -v
```

`examples/` 目录下包含 SQLAlchemy、SQLModel、Tortoise ORM 三套完整的 FastAPI 示例应用，覆盖上传、预览、提交落库、导出的全 HTTP 端到端流程，均使用 SQLite 内存数据库。

## 许可协议

[MIT](LICENSE)
