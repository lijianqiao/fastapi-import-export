# fastapi_import_export

FastAPI 优先的导入导出工具库，保持业务模型解耦。

## 主要特性

- 异步优先的导入/导出生命周期钩子。
- 显式 Resource 映射，避免 ORM 强耦合。
- 可选后端：解析/存储/校验按需启用。
- 导出支持流式输出，适配大数据集。

## 环境要求

- Python 3.14+
- FastAPI 0.128+

## 版本兼容矩阵

| 组件       | 支持范围 | 说明                         |
| ---------- | -------- | ---------------------------- |
| Python     | 3.14+    | 面向异步工作流测试。         |
| FastAPI    | 0.128+   | 使用 UploadFile 与异步端点。 |
| Pydantic   | 2.x      | 模型基于 BaseModel。         |
| polars     | 1.x      | 可选解析/校验后端。          |
| openpyxl   | 3.x      | Excel 解析后端。             |
| SQLAlchemy | 2.x      | 可选，仅用于完整性错误提示。 |

## 为什么不是 django-import-export

- Django 生态的 ORM/Admin 强耦合不适配 FastAPI 的异步工作流。
- 本库以异步为先，定位为工具库而非框架。
- 提供稳定、可组合的 API 与显式生命周期钩子。

## 核心边界

- 不管理数据库连接。
- 不接管 ORM，仅做适配。
- 不处理权限鉴权。
- 不处理文件存储（仅提供可选后端）。

## 安装

最小安装（仅核心）：

```bash
pip install fastapi-import-export
```

常用可选依赖：

```bash
pip install fastapi-import-export[polars,xlsx,storage]
```

完整依赖：

```bash
pip install fastapi-import-export[full]
```

## 可选依赖说明

- polars: DataFrame 解析与校验后端。
- xlsx: Excel 解析支持（openpyxl）。
- storage: 文件系统存储后端。
- sqlalchemy: SQLAlchemy 相关可选支持。
- full: 全量可选依赖。

## 快速开始

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
from fastapi_import_export import Importer


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)
```

### 3) FastAPI 接入示例

```python
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

## 可选后端门面

- parse/storage/validation/db_validation 为惰性加载门面。
- 缺少可选依赖时会抛出 ImportExportError 并提示安装方式。

## 端到端示例

下面是一个最小的端到端流程，覆盖上传、校验、预览、提交。

```python
from fastapi import APIRouter, UploadFile

from fastapi_import_export import Importer, Resource
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import ImportExportService


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
        validate_fn=validate_fn,
    )


@router.get("/import/preview")
async def import_preview(import_id: str, checksum: str, page: int = 1, page_size: int = 50):
    return await svc.preview(
        import_id=import_id,
        checksum=checksum,
        page=page,
        page_size=page_size,
        kind="all",
    )


@router.post("/import/commit")
async def import_commit(body: ImportCommitRequest):
    return await svc.commit(body=body, persist_fn=persist_fn)
```

## FAQ

**为什么会提示缺少依赖？**

安装对应的 extras，例如：

```bash
pip install fastapi-import-export[polars,xlsx,storage]
```

**为什么包根不再导出 ImportExportService？**

请从 service 模块导入：

```python
from fastapi_import_export.service import ImportExportService
```

**为什么校验后数据被过滤？**

服务类会将校验失败的行从 `valid.parquet` 中剔除。
如需查看原始解析数据，请使用 `kind=all` 预览。

## 常见错误排查

- **上传文件过大**：创建 `ImportExportService` 时提高 `max_upload_mb`。
- **checksum 不匹配**：确保客户端使用 `upload_parse_validate` 返回的 checksum。
- **missing_dependency**：安装解析/存储/校验对应的 extras。
- **db_conflict**：检查唯一约束与软删除记录是否导致冲突。

## 迁移提示

- ImportExportService 和 ExportResult 不再从包根导出，
  如仍需使用请从 fastapi_import_export.service 导入。

## 许可协议

MIT
