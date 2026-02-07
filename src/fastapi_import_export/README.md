# fastapi_import_export

一个可复用的 FastAPI 导入导出基础库（上传→解析→校验→预览→提交、导出 CSV/Excel、模板生成、临时文件清理）。

本库只提供通用基础设施：具体业务字段规则（例如“设备导入导出”）通过注入 handler（validate/persist/export/template）实现。

## 依赖

- fastapi
- sqlalchemy
- pydantic
- polars
- openpyxl
- uuid6
- 可选：redis（或兼容客户端，用于导入提交锁）

## 快速开始

```python
from fastapi_import_export import ImportExportService

svc = ImportExportService(
    db=db,                       # 任意对象，原样传递给你的 handler
    redis_client=redis_client,   # 可选
    base_dir=None,               # 可选；默认从环境变量或系统临时目录推导
    max_upload_mb=20,
    lock_ttl_seconds=300,
)
```

环境变量（可选）：

- IMPORT_EXPORT_BASE_DIR / IMPORT_EXPORT_TMP_DIR：导入导出根目录
- IMPORT_EXPORT_IMPORTS_DIRNAME：imports 子目录名（默认 imports）
- IMPORT_EXPORT_EXPORTS_DIRNAME：exports 子目录名（默认 exports）

更多端到端 FastAPI 接入示例、handler 签名、存储结构说明，请参考仓库内的适配说明或自行按需封装路由。

## Validation Core / 校验核心

本库默认只提供“校验核心原语”，用于收集错误与读取字段值，不包含任何业务规则（例如 IP/枚举/正则/范围校验）。

By default, this library only provides core validation primitives for collecting errors and reading values. It intentionally does NOT include business rules (IP/enum/regex/range checks).

### ErrorCollector & RowContext

```python
from fastapi_import_export import ErrorCollector, RowContext

errors: list[dict] = []
collector = ErrorCollector(errors)

for r in rows:
    ctx = RowContext(collector=collector, row_number=int(r["row_number"]), row=r)
    value = ctx.get_str("name")
    if not value:
        ctx.add(field="name", message="name is required")
```

## Validation Extras (Optional) / 校验扩展（可选）

如果你希望减少样板代码，可以显式引入 `validation_extras` 中的 `RowValidator`（包含 IP/枚举/正则等规则）。这是可选能力，不属于默认“通用核心”。

If you want less boilerplate, you can explicitly import `RowValidator` from `validation_extras` (IP/enum/regex rules). This is optional and not part of the default core.

```python
from fastapi_import_export.validation_extras import RowValidator

errors: list[dict] = []
for r in rows:
    v = RowValidator(errors=errors, row_number=int(r["row_number"]), row=r)
    v.not_blank("name", "name is required")
    v.ip_address("ip_address", "invalid ip")
```

## DB Checks / 数据库校验扩展（推荐）

本库未来会被复用到不同 FastAPI 项目中，因此更推荐使用“数据库校验扩展接口”，让业务侧只实现“怎么查库”，通用库负责把冲突结果映射回 `row_number` 并返回统一错误结构。

This library is intended for reuse across FastAPI projects. A recommended approach is using the "DB checks" extension: your domain only implements "how to query the database", while this library maps conflicts back to `row_number` and produces consistent error items.

### 核心接口 / Core API

- `DbCheckSpec`: 声明 key_fields（用于拼 key）、check_fn（业务查库函数）与默认 message。
- `db_check_fn(db, keys, allow_overwrite=...) -> dict[key_tuple, info]`：返回冲突映射，通用库会自动生成行级错误。

### 示例 / Example

```python
from fastapi_import_export import DbCheckSpec

async def check_ip_conflict(db, keys, *, allow_overwrite: bool = False):
    # keys: list[tuple[str, ...]]，比如 [("10.0.0.1",), ("10.0.0.2",)]
    # 业务侧实现：查库后返回冲突 key -> info
    conflicts = {}
    # conflicts[key] = {"message": "IP 已存在", "details": {"is_deleted": False}}
    return conflicts

spec = DbCheckSpec(
    key_fields=["ip_address"],
    check_fn=check_ip_conflict,
    field="ip_address",
    message="IP 冲突",
    type="db_unique",
)
```
