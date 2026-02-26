# 计划：ORM 适配层 + Widgets + 易用性增强

> 本计划用于下一阶段改进，聚焦“声明式体验”与“零心智负担”。

## 目标
- 简单 CRUD 场景接近 “django-import-export” 的声明式体验。
- 不污染主 API，不接管 FastAPI，扩展点受控。
- 让用户不必理解 Polars/ORM 细节也能完成导入导出。

## 已确认的决策
- 优先支持 ORM：**SQLAlchemy + SQLModel + Tortoise**（三者都做）。
- 默认持久化策略：**只插入（no upsert）**。

## 总体方案
新增一个**可选适配层（contrib）**，基于 ORM 自动提供：
- 默认 `validate_fn`
- 默认 `persist_fn`
- 默认 `query_fn`

并提供一个轻量 **Widgets / FieldCodec** 系统解决枚举/日期/Decimal 等转换。

## 新增 API（建议形态）
> 不直接放到顶层主 API，放在 `fastapi_import_export.contrib.*` 下。

### ORM 导入（声明式）
```python
result = await import_model_csv(
    file,
    model=Book,
    db=session,
    unique_fields=["isbn"],
)
```

### ORM 导出（声明式）
```python
payload = await export_model_csv(
    model=Book,
    db=session,
    filters={"status": "available"},
)
```

### 可选参数（保持少量）
- `columns`: 指定字段顺序/子集
- `filters`: 等值过滤（最小可用）
- `unique_fields`: DB 唯一性检查
- `options`: 复用 `ExportOptions` / `ImportOptions`

## 模块设计
```
fastapi_import_export/
  contrib/
    sqlalchemy/
      import_model.py
      export_model.py
      adapters.py
    sqlmodel/
      ...
    tortoise/
      ...
  codecs/
    base.py (Codec Protocol)
    builtins.py (Enum/Date/Datetime/Decimal/Bool)
  helpers/
    rows.py (iter_rows / rows_to_dicts)
```

## ORM 适配默认行为
### Import
- 自动生成 `validate_fn`：
  - 非空字段校验（nullable=False）
  - 基础类型转换失败报错
  - `unique_fields` 触发 DB 检查
- 默认 `persist_fn`：
  - 批量插入（no upsert）
  - 事务内提交

### Export
- 默认 `query_fn`：
  - `select(model)`
  - 支持 `filters`（等值过滤）
- 默认输出为 `list[dict]`

## Widgets / FieldCodec 系统
### 目的
解决“枚举↔中文/日期/Decimal”等常见转换的手动负担。

### 设计
- `Codec[T]` 协议
  - `parse(str) -> T`
  - `format(T) -> str`
- 内置 codecs：
  - Enum / date / datetime / Decimal / bool
- 绑定方式：
  - `Resource.field_codecs: dict[str, Codec]`
  - ORM adapter 可根据字段类型自动绑定

## Polars 心智降低
新增 helper：
- `iter_rows(df)`：返回 `dict` 迭代器
- `rows_to_dicts(df)`：直接转 list[dict]

文档中建议使用 helper，而非直接 `df.iter_rows(...)`。

## 文档规划
### 文档分层清晰化
1. **Easy Layer**：声明式 ORM 适配入口（contrib）
2. **Options Layer**：`ExportOptions` / `ImportOptions`
3. **Advanced Layer**：自定义 hook（Importer/Exporter/Service）

### 明确签名与约定
- `validate_fn` 的 `df` 类型：明确为 `polars.DataFrame`
- `ImportOptions.db`：强调会自动传入 validate/persist
- errors 格式：`row_number` 从 1 开始、`field` 为规范字段名

## 测试计划
- ORM adapter end-to-end（SQLAlchemy / SQLModel / Tortoise）
- codecs（Enum/date/datetime/Decimal/bool）
- helper（iter_rows/rows_to_dicts）
- 适配层与 easy layer 联动

## 兼容性与风险
- **不修改现有 easy/advanced 语义**，只新增贡献模块。
- ORM adapter 只覆盖“80% CRUD”，复杂规则仍需 advanced hooks。

---

## ORM 适配实现细节（补充）

### 统一接口规范（Contrib API）
> 仅提供异步接口；同步 ORM 不在本阶段支持。

**SQLAlchemy / SQLModel**
```python
async def import_model_csv(
    file: UploadFile,
    *,
    model: type,
    db: AsyncSession,
    unique_fields: list[str] | None = None,
    columns: list[str] | None = None,
    options: ImportOptions | None = None,
) -> ImportResult[ImportErrorItem]: ...

async def export_model_csv(
    *,
    model: type,
    db: AsyncSession,
    filters: dict[str, object] | None = None,
    columns: list[str] | None = None,
    options: ExportOptions | None = None,
) -> ExportPayload: ...
```

**Tortoise ORM**
```python
async def import_model_csv(
    file: UploadFile,
    *,
    model: type,
    unique_fields: list[str] | None = None,
    columns: list[str] | None = None,
    options: ImportOptions | None = None,
) -> ImportResult[ImportErrorItem]: ...

async def export_model_csv(
    *,
    model: type,
    filters: dict[str, object] | None = None,
    columns: list[str] | None = None,
    options: ExportOptions | None = None,
) -> ExportPayload: ...
```

### 适配层默认行为（Import）
1. **解析与列归一化**
   - 仍使用 Polars 解析（与现有 `parse` 保持一致）。
   - 列名使用 `columns` 参数或模型字段顺序。
2. **类型转换**
   - 根据 ORM 字段类型映射 codec（Enum/date/datetime/Decimal/bool）。
   - 转换失败生成校验错误（`type="format"`）。
3. **必填校验**
   - `nullable=False` 字段缺失或空值生成 `required` 错误。
4. **唯一性校验**
   - 仅支持 `unique_fields` 指定字段（不自动扫描所有 unique 约束）。
   - `allow_overwrite=True` 时跳过唯一性校验（不自动 upsert）。
5. **持久化**
   - SQLAlchemy/SQLModel：`insert(model)` 批量插入。
   - Tortoise：`bulk_create`。
   - 默认不 upsert；仍可能触发 DB 约束错误。

### 适配层默认行为（Export）
1. **查询**
   - SQLAlchemy/SQLModel：`select(model).where(...)`。
   - Tortoise：`model.filter(**filters)`。
2. **过滤规则**
   - `filters` 为等值过滤。
   - 当值为 `list/tuple/set` 时使用 `IN`。
3. **输出**
   - `list[dict]` 作为 `export_*` 的数据源。
   - 列顺序：`columns` > 模型字段顺序。

### 字段与列顺序规则
- 默认列顺序使用模型字段声明顺序（SQLAlchemy/SQLModel）或 Model 字段定义顺序（Tortoise）。
- `columns` 参数覆盖顺序并支持字段子集。

### 错误格式约定
- `row_number` 从 1 开始（不含表头）。
- `field` 为规范化字段名（模型字段名）。
- `message` 同时提供中英文描述（与现有风格一致）。

### 适配层扩展点
- **自定义 codec**：允许用户注册 `field_codecs` 覆盖默认推断。
- **自定义过滤器**：高级用户可替换默认 `filters` 构造逻辑。
- **自定义持久化策略**：允许传入 `persist_fn` 覆盖默认批量插入。

---

# 补充计划：Easy Layer Codecs 自动应用 + Resource 模型绑定增强

> 解决现有问题：Easy Layer 未自动应用 `field_codecs`，ORM 实例导出为空，导入时仍为字符串。

## 目标
- Easy Layer 自动应用 codecs（导入 parse / 导出 format），无需用户在 `validate_fn/persist_fn` 中手写转换。
- 支持 `Resource.model` 推断字段顺序（保持“显式优先”）。
- 不改变 advanced 层语义；对现有用户尽量兼容。

## 决策与规则
- **显式优于隐式**：`field_aliases` 覆盖自动映射。
- **未声明字段时推断**：
  - Source：`model.__table__.columns`（SQLAlchemy/SQLModel）或 `model._meta`（Tortoise）
  - 自动排除：`id` / `created_at` / `updated_at` / soft-delete 标记
  - 可配置：`exclude_fields = ["password"]`
- **Codec 自动应用范围**：
  - Import（Easy）：在 `validate_fn/persist_fn` 之前 decode
  - Export（Easy）：在输出前对值 format
- **错误策略**：codec parse 失败 → 生成 `type="format"` 的错误条目，并从 valid_rows 剔除。

## 实现步骤
1. **Easy Import 自动 decode**
   - 在 `easy._import_file` 内包装 `validate_fn`：
     - 读取 `df.to_dicts()` → 按 `resource.field_codecs` 对字段 `parse`。
     - 生成新的 `polars.DataFrame`（保留 `row_number`）。
     - parse 失败时追加 errors（`row_number/field/message/type="format"`）。
   - 将转换后的 `df` 传给原始 `validate_fn` / `persist_fn`。

2. **Easy Export 自动 format**
   - `_normalize_rows` 支持 ORM 实例：
     - 若 row 非 Mapping 且存在 `resource.field_order()`，按字段 `getattr` 抽取值。
   - 对每个字段，如果存在 codec，则 `format(value)`。

3. **模型字段推断完善**
   - `Resource.field_order()` 已支持 `model` 推断；确认：
     - 仅当未声明字段时生效。
     - `exclude_fields` 生效且默认排除主键/时间戳/软删字段。

## 测试计划（新增）
- `test_easy_import_codecs`：验证 Enum/Date/Decimal 自动转换（validate_fn 接收的类型为 Enum/date/Decimal）。
- `test_easy_export_model_rows`：ORM 实例列表导出非空且列正确（使用 SQLAlchemy/SQLModel）。
- `test_codec_parse_error`：非法值产生 format 错误且 valid_rows 过滤。
- `test_resource_model_binding_default_exclude`：默认排除 id/created_at/updated_at/soft-delete 字段。

## 文档更新（补充）
- README / RTD / Skill：
  - 明确 Easy Layer 自动应用 codecs（导入/导出）
  - 说明 ORM 实例导出规则
  - Resource.model 推断规则与 `exclude_fields`

## 兼容性说明
- 对已有用户：若未配置 `field_codecs` 或 `model`，行为保持不变。
- 若配置 codecs：导入/导出将发生类型转换，预期与“显式配置优先”一致。
