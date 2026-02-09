# fastapi_import_export

FastAPI を優先したインポート/エクスポート用ユーティリティ。ドメインモデルの分離を保ちます。

他の言語: [README.md](README.md) | [README_CN.md](README_CN.md)

## 主な特長

- インポート/エクスポートのライフサイクルフックは非同期優先。
- Resource を明示的にマッピングし、ORM との強い結合を回避。
- 解析/保存/検証は必要に応じて切り替え可能なプラガブルバックエンド。
- 大規模データに対応したストリーミング出力。

## 動作環境

- Python 3.12-3.14
- FastAPI 0.128+

## 互換性マトリクス

| コンポーネント | 対応範囲  | 補足                                      |
| -------------- | --------- | ----------------------------------------- |
| Python         | 3.12-3.14 | 非同期ワークフロー向けに検証。            |
| FastAPI        | 0.128+    | UploadFile と非同期エンドポイントを使用。 |
| Pydantic       | 2.x       | BaseModel を利用。                        |
| polars         | 1.x       | デフォルトで同梱。                        |
| openpyxl       | 3.x       | デフォルトで同梱。                        |

## django-import-export を使わない理由

- Django の ORM/Admin 依存は FastAPI の非同期ワークフローに不適合。
- 本ライブラリは非同期優先で、フレームワークではなくツールキットとして設計。
- 明示的なライフサイクルフックを持つ安定した合成可能 API。

## コアの境界

- DB 接続は管理しない。
- ORM を所有せず、適応のみ。
- 認可/認証は扱わない。
- ストレージは所有しない（プラガブルバックエンドのみ）。

## インストール

標準インストール（バッテリー同梱）：

```bash
pip install fastapi-import-export
# または
uv add fastapi-import-export
```

Polars/XLSX/ストレージ補助はデフォルトで含まれます。ORM アダプタは任意です：

```bash
pip install fastapi-import-export[sqlalchemy]
# または
pip install fastapi-import-export[sqlmodel]
# または
pip install fastapi-import-export[tortoise]
# または
uv add fastapi-import-export[sqlalchemy]
# または
uv add fastapi-import-export[sqlmodel]
# または
uv add fastapi-import-export[tortoise]
```

必要に応じて DB ドライバ（例: `asyncpg`、`aiomysql`）を別途インストールしてください。

開発・ユニットテスト依存：

```bash
pip install fastapi-import-export pytest pytest-asyncio pytest-cov anyio
# または
uv add --group dev fastapi-import-export pytest pytest-asyncio pytest-cov anyio
```

E2E 統合テスト依存（任意、サンプルアプリ実行用）：

```bash
pip install fastapi-import-export[sqlalchemy] httpx python-multipart aiosqlite
# または
uv add --group e2e fastapi-import-export[sqlalchemy] httpx python-multipart aiosqlite
```

## クイックスタート（易用層）

### 1) Resource を定義

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

### 2) CSV/XLSX を一発インポート

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

### 3) CSV/XLSX をエクスポート

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

## ORM アダプタ（任意）

ORM アダプタは `fastapi_import_export.contrib` にあり、SQLAlchemy/SQLModel/Tortoise をサポートします。
インストール方法：

```bash
pip install fastapi-import-export[sqlalchemy]
# または
pip install fastapi-import-export[sqlmodel]
# または
pip install fastapi-import-export[tortoise]
```

得られるもの：

- ORM モデルのフィールド自動推論（列順・必須判定）。
- 自動型変換（Enum/Date/Datetime/Decimal/Bool）。
- `field_codecs` / `__import_export_codecs__` でフィールド単位に上書き可能。

## Codecs（Widget システム）

Codecs は一般的な型の import/export 変換を担当します。
Enum/Date/Datetime/Decimal/Bool を内蔵し、フィールド単位で拡張できます。
Easy レイヤーは `validate_fn/persist_fn` の前に codecs を適用し、
エクスポート時に値をフォーマットします。

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

## Resource モデルバインディング（軽量）

Resource が `model` を宣言し、**フィールドを明示しない**場合、
ORM モデルから自動推論します：

- 取得元：`model.__table__.columns`（SQLAlchemy/SQLModel）または `model._meta`（Tortoise）
- 自動除外：主キー（`id`）、`created_at`、`updated_at`、ソフトデリート系
- 任意除外：`exclude_fields = ["password"]`
- 明示優先：`field_aliases` が自動マッピングを常に上書き

```python
class BookResource(Resource):
    model = Book
    exclude_fields = ["password"]
    field_aliases = {"Author": "author"}  # 自動マッピングを上書き
```

## 高度（Hooks）

高度な API は `fastapi_import_export.advanced` にあります。

### 1) Resource を定義

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

### 2) Importer を組み立て

```python
from fastapi_import_export.advanced import Importer


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)
```

### 3) FastAPI への組み込み

```python
from uuid import UUID

from fastapi import APIRouter, UploadFile


router = APIRouter()


@router.post("/import")
async def import_data(file: UploadFile):
    result = await importer.import_data(file=file, resource=UserResource)
    return result
```

## 非同期インポート例

```python
async def validate_fn(*, data, resource, allow_overwrite=False):
    return data, []


async def persist_fn(*, data, resource, allow_overwrite=False):
    return 100
```

## 大規模エクスポート（ストリーミング）

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

## Exporter 使用例

Excel で CSV が文字化けする場合は、UTF-8 BOM を付与してください（`utf-8-sig`）。

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

## プラガブルバックエンドのファサード

- parse/storage/validation/db_validation は遅延読み込みのファサード。
- バンドル済み依存を外した場合や任意アダプタ/ドライバ未導入時に
  missing_dependency を返します。

## アップロード許可リスト設定

優先順位: 呼び出し単位の上書き > resolve_config の引数 > 環境変数 > 既定値。

呼び出し単位の上書き：

```python
await svc.upload_parse_validate(
    file=file,
    column_aliases=UserResource.field_mapping(),
    validate_fn=service_validate_fn,
    allowed_extensions=[".csv"],
    allowed_mime_types=["text/csv"],
)
```

設定レベルの上書き：

```python
from fastapi_import_export.config import resolve_config


cfg = resolve_config(
    allowed_extensions=[".csv", ".xlsx"],
    allowed_mime_types=["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
)
svc = ImportExportService(db=object(), config=cfg)
```

環境変数の例：

```bash
export IMPORT_EXPORT_ALLOWED_EXTENSIONS=".csv,.xlsx"
export IMPORT_EXPORT_ALLOWED_MIME_TYPES="text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

## 一意制約の衝突検出

インポートデータのコミット時、ライブラリはデータベースの一意制約違反を自動検出し、
ユーザーフレンドリーなエラーレスポンスを返します。
`constraint_parser` モジュールは 5 つのデータベースの正確なエラー解析をサポートします：

| データベース    | エラーパターン                                        | 抽出情報         |
| --------------- | ----------------------------------------------------- | ---------------- |
| PostgreSQL      | `Key (col)=(val) already exists.`                     | 列名、値、制約名 |
| MySQL / MariaDB | `Duplicate entry 'val' for key 'key_name'`            | 値、制約名       |
| SQLite          | `UNIQUE constraint failed: table.col`                 | 列名             |
| SQL Server      | `Violation of UNIQUE KEY constraint 'name'`           | 値、制約名       |
| Oracle          | `ORA-00001: unique constraint (SCHEMA.NAME) violated` | 制約名           |

パーサーをビジネスコードで直接使用することもできます：

```python
from fastapi_import_export.advanced import ConstraintDetail, parse_unique_constraint_error

detail: ConstraintDetail | None = parse_unique_constraint_error(
    str(exc), detail_text=getattr(getattr(exc, "orig", None), "detail", "")
)
if detail:
    print(detail.db_type, detail.columns, detail.values)
```

## エンドツーエンド例

アップロード、検証、プレビュー、コミットを含む最小構成の流れです。

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


# 任意: サービスクラスでアップロード/プレビュー/コミットのワークフロー
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

**依存関係が不足していると表示されるのはなぜですか？**

バンドル依存を削除したか、未導入のアダプタ/ドライバを使っています
（例: ORM アダプタを使うが対応する extra を入れていない）。
ベースパッケージの再インストール、または必要な依存を追加してください。

**検証後にデータがフィルタされるのはなぜですか？**

サービスクラスは検証に失敗した行を `valid.parquet` から除外します。
元の解析データを見る場合は `kind=all` でプレビューしてください。

## トラブルシューティング

- **アップロードが大きすぎる**: `ImportExportService` 作成時に `max_upload_mb` を増やしてください。
- **checksum が一致しない**: `upload_parse_validate` が返した checksum をクライアントで使用してください。
- **missing_dependency**: バンドル依存の復元、または必要なアダプタ/ドライバを追加してください。
- **db_conflict**: 一意制約や論理削除レコードの影響を確認してください。

## テスト

ユニットテストの実行（依存のインストールは [インストール](#インストール) を参照）：

```bash
pytest tests/ -v
```

E2E 統合テストの実行：

```bash
pytest examples/ -v
```

`examples/` ディレクトリには SQLAlchemy・SQLModel・Tortoise ORM の 3 つの完全な FastAPI サンプルアプリが含まれ、アップロード・プレビュー・コミット・エクスポートの HTTP エンドツーエンドフローをインメモリ SQLite で検証します。

## ライセンス

[MIT](LICENSE)
