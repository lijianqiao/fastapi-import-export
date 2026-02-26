# Release 说明（vNext）

> 用于 GitHub Release 的说明草案，可按版本号替换标题。

关联修复计划： [FixPlan_2026-02-26](FixPlan_2026-02-26.md)

## 亮点
- 新增易用层 API：`export_csv` / `export_xlsx` / `import_csv` / `import_xlsx`，5 分钟可跑通。
- 新增显式配置层：`ExportOptions` / `ImportOptions`，覆盖 80% 场景。
- 高级扩展能力收敛到 `fastapi_import_export.advanced` 命名空间，主 API 极简。

## 破坏性变更
- 顶层 `__all__` 缩减，仅保留易用层与必要类型。
- 原 `Importer/Exporter/ImportExportService` 改为从 `fastapi_import_export.advanced` 导入。

## 迁移指南
- 旧用法：
  - `from fastapi_import_export import Importer`
  - `from fastapi_import_export import Exporter`
  - `from fastapi_import_export import ImportExportService`
- 新用法：
  - `from fastapi_import_export.advanced import Importer`
  - `from fastapi_import_export.advanced import Exporter`
  - `from fastapi_import_export.advanced import ImportExportService`
- 新用户推荐直接使用顶层 `export_*` / `import_*` API。

## 新增模块
- `formats.py`：格式枚举与默认 media_type。
- `options.py`：显式配置数据类。
- `serializers.py`：内置 CSV/XLSX 序列化器。
- `renderers.py`：字节流渲染与分块。
- `easy.py`：易用层入口。
- `advanced/__init__.py`：高级 API 命名空间。

## 行为与默认值
- CSV 默认不带 BOM。
- CSV 默认 `\\r\\n` 行分隔。
- `media_type` 自动推导。
- 列顺序：`options.columns` > `Resource` 字段顺序 > 推断。
- 导出映射：`export_aliases` > 可逆 `field_aliases` > identity。

## 修复
- 有效行数为 0 且无错误时仍可提交（`imported_rows=0`）。
- 易用层 allowlist 传空列表可关闭限制。
- `BuildTemplateFn` 签名与 service 层对齐。
- 文档描述修正。

## 文档与测试
- README（中/英/日）Quick Start 改为易用层。
- ReadTheDocs 标准文档骨架与高级扩展点说明。
- 新增易用层与导出映射相关测试。
