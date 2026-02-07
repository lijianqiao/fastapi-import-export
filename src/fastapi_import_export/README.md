# fastapi_import_export

FastAPI 优先的导入导出工具库，保持业务模型解耦。

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
from fastapi_import_export import Importer


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

## ORM 适配示例

```python
async def query_fn(*, resource, params=None):
    return data
```
