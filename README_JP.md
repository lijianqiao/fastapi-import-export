# fastapi_import_export

FastAPI を優先したインポート/エクスポート用ユーティリティ。ドメインモデルの分離を保ちます。

他の言語: [README.md](README.md) | [README_CN.md](README_CN.md)

## 主な特長

- インポート/エクスポートのライフサイクルフックは非同期優先。
- Resource を明示的にマッピングし、ORM との強い結合を回避。
- 解析/保存/検証は必要に応じて有効化できるオプションバックエンド。
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
| polars         | 1.x       | 解析/検証のオプションバックエンド。       |
| openpyxl       | 3.x       | Excel 解析バックエンド。                  |

## django-import-export を使わない理由

- Django の ORM/Admin 依存は FastAPI の非同期ワークフローに不適合。
- 本ライブラリは非同期優先で、フレームワークではなくツールキットとして設計。
- 明示的なライフサイクルフックを持つ安定した合成可能 API。

## コアの境界

- DB 接続は管理しない。
- ORM を所有せず、適応のみ。
- 認可/認証は扱わない。
- ストレージは所有しない（オプションバックエンドのみ）。

## インストール

最小構成（コアのみ）：

```bash
pip install fastapi-import-export
```

よく使うオプション依存：

```bash
pip install fastapi-import-export[polars,xlsx,storage]
```

全オプション依存：

```bash
pip install fastapi-import-export[full]
```

## オプション依存の説明

- polars: DataFrame の解析/検証バックエンド。
- xlsx: Excel 解析サポート（openpyxl）。
- storage: ファイルシステム保存バックエンド。
- full: すべてのオプション依存。

## クイックスタート

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
from fastapi_import_export import Importer


importer = Importer(
    parser=parse_fn,
    validator=validate_fn,
    transformer=transform_fn,
    persister=persist_fn,
)
```

### 3) FastAPI への組み込み

```python
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

## オプションバックエンドのファサード

- parse/storage/validation/db_validation は遅延読み込みのファサード。
- オプション依存が不足すると ImportExportError を送出し、インストール手順を提示。

## アップロード許可リスト設定

優先順位: 呼び出し単位の上書き > resolve_config の引数 > 環境変数 > 既定値。

呼び出し単位の上書き：

```python
await svc.upload_parse_validate(
    file=file,
    column_aliases=UserResource.field_mapping(),
    validate_fn=validate_fn,
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

## エンドツーエンド例

アップロード、検証、プレビュー、コミットを含む最小構成の流れです。

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


# 任意: サービスクラスでアップロード/プレビュー/コミットのワークフロー
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

**依存関係が不足していると表示されるのはなぜですか？**

該当する extras をインストールしてください。例：

```bash
pip install fastapi-import-export[polars,xlsx,storage]
```

**ImportExportService がパッケージ直下から取得できないのはなぜですか？**

service モジュールからインポートしてください：

```python
from fastapi_import_export.service import ImportExportService
```

**検証後にデータがフィルタされるのはなぜですか？**

サービスクラスは検証に失敗した行を `valid.parquet` から除外します。
元の解析データを見る場合は `kind=all` でプレビューしてください。

## トラブルシューティング

- **アップロードが大きすぎる**: `ImportExportService` 作成時に `max_upload_mb` を増やしてください。
- **checksum が一致しない**: `upload_parse_validate` が返した checksum をクライアントで使用してください。
- **missing_dependency**: 解析/保存/検証の extras をインストールしてください。
- **db_conflict**: 一意制約や論理削除レコードの影響を確認してください。

## 移行メモ

- ImportExportService と ExportResult はパッケージ直下からは公開されません。
  既存コードでは fastapi_import_export.service からインポートしてください。

## ライセンス

[MIT](LICENSE)
