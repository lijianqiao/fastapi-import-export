# 重构说明（vNext）

## 目标
- 让 80% 用户 5 分钟跑通，不理解 pipeline 也能完成导入导出。
- 保留高级扩展能力，但不污染主 API。
- 外部 API 极度克制，内部结构高度可扩展。

## 主要改动
### 1) 三层 API 结构
- 易用层（零配置）：顶层 `export_*` / `import_*` 函数。
- 显示配置层：`ExportOptions` / `ImportOptions` 控制常见行为。
- 高级扩展层：`fastapi_import_export.advanced` 命名空间保留 hook 生态。

### 2) 顶层 API 收敛（Breaking）
- 新增顶层函数：
  - `export_csv(source, *, resource=None, params=None, options=None)`
  - `export_xlsx(source, *, resource=None, params=None, options=None)`
  - `import_csv(file, *, resource, validate_fn, persist_fn, options=None)`
  - `import_xlsx(file, *, resource, validate_fn, persist_fn, options=None)`
- 顶层 `__all__` 缩减，仅保留易用层与必要类型。
- 原 `Importer/Exporter/ImportExportService` 迁移到 `fastapi_import_export.advanced`。

### 3) 新增模块
- `formats.py`：格式枚举与默认 `media_type`、扩展名。
- `options.py`：`ExportOptions` / `ImportOptions`。
- `serializers.py`：内置 CSV/XLSX 序列化器。
- `renderers.py`：字节流渲染（chunk/stream）。
- `easy.py`：易用层的导入导出入口。
- `advanced/__init__.py`：高级 API 命名空间。

### 4) Resource 导出映射
- 新增 `export_aliases` 与 `export_mapping()`。
- 映射规则：
  - `export_aliases` 优先
  - `field_aliases` 可逆则反转
  - 否则回退为字段名自身

### 5) 默认行为调整
- CSV 默认不带 BOM。
- CSV 默认 `\r\n` 行分隔。
- `media_type` 由格式推导。
- 列顺序优先级：`options.columns` > `Resource` 字段顺序 > 推断。

## 关键修复
- `valid_df` 为空且无错误时仍写入 `valid.parquet`，`commit` 可返回 `imported_rows=0`。
- 易用层 allowlist 允许传空列表关闭限制（不再 `or` 回退默认值）。
- `BuildTemplateFn` 签名与 service 层对齐。
- `_import_file` 文档说明修正为通用描述。

## 文档与测试
- README（中/英/日）Quick Start 改为易用层示例。
- ReadTheDocs 增加标准骨架与高级扩展点说明。
- 新增易用层测试与导出映射测试。

## 迁移提示
- 原 `from fastapi_import_export import Importer/Exporter/ImportExportService`
  改为 `from fastapi_import_export.advanced import ...`
- 推荐新用户使用顶层 `export_*` / `import_*` API。
