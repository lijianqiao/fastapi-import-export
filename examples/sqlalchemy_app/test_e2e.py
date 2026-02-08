"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_e2e.py
@DateTime: 2026-02-08
@Docs: End-to-end tests for SQLAlchemy example app.
SQLAlchemy 示例应用的端到端测试。
"""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import Device


@pytest.mark.asyncio
class TestSQLAlchemyE2E:
    """SQLAlchemy end-to-end import/export tests.
    SQLAlchemy 端到端导入导出测试。
    """

    async def test_upload_csv(self, client: AsyncClient, csv_path: Path) -> None:
        """Upload CSV -> 200, 5 valid rows / 上传 CSV -> 200, 5 有效行。"""
        with open(csv_path, "rb") as f:
            resp = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 5
        assert data["valid_rows"] == 5
        assert data["error_rows"] == 0

    async def test_upload_xlsx(self, client: AsyncClient, xlsx_path: Path) -> None:
        """Upload XLSX -> 200, 5 rows / 上传 XLSX -> 200, 5 行。"""
        with open(xlsx_path, "rb") as f:
            resp = await client.post(
                "/import/upload",
                files={
                    "file": ("devices.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                },
            )
        assert resp.status_code == 200
        assert resp.json()["total_rows"] == 5

    async def test_preview_all(self, client: AsyncClient, csv_path: Path) -> None:
        """Preview kind=all shows 5 rows / 预览 kind=all 显示 5 行。"""
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()

        resp = await client.get(
            f"/import/{data['import_id']}/preview",
            params={"checksum": data["checksum"], "kind": "all"},
        )
        assert resp.status_code == 200
        preview = resp.json()
        assert preview["total_rows"] == 5
        assert len(preview["rows"]) == 5

    async def test_preview_valid(self, client: AsyncClient, csv_path: Path) -> None:
        """Preview kind=valid shows 5 rows / 预览 kind=valid 显示 5 行。"""
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()

        resp = await client.get(
            f"/import/{data['import_id']}/preview",
            params={"checksum": data["checksum"], "kind": "valid"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_rows"] == 5

    async def test_commit_success(self, client: AsyncClient, csv_path: Path) -> None:
        """Commit -> 200, status=committed, imported_rows=5 / 提交 -> 200。"""
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()

        resp = await client.post(
            f"/import/{data['import_id']}/commit",
            params={"checksum": data["checksum"]},
        )
        assert resp.status_code == 200
        commit = resp.json()
        assert commit["status"] == "committed"
        assert commit["imported_rows"] == 5

    async def test_commit_verifies_database(
        self,
        client: AsyncClient,
        csv_path: Path,
        db_session: tuple[async_sessionmaker[AsyncSession], str],
    ) -> None:
        """After commit, database has 5 Device records / 提交后数据库有 5 条设备记录。"""
        factory, _ = db_session
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()
        await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})

        async with factory() as session:
            result = await session.execute(select(Device))
            devices = result.scalars().all()
            assert len(devices) == 5
            names = {d.name for d in devices}
            assert "switch-01" in names
            assert "firewall-01" in names

    async def test_export_after_commit(self, client: AsyncClient, csv_path: Path) -> None:
        """Export after commit returns CSV with device data / 提交后导出返回含设备数据的 CSV。"""
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()
        await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})

        resp = await client.get("/export")
        assert resp.status_code == 200
        body = resp.text
        assert "switch-01" in body
        assert "192.168.1.1" in body

    async def test_commit_idempotent(self, client: AsyncClient, csv_path: Path) -> None:
        """Second commit returns committed without error / 第二次提交幂等返回。"""
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()

        await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})
        resp2 = await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "committed"

    async def test_upload_with_validation_errors(self, client: AsyncClient, tmp_path: Path) -> None:
        """Upload with invalid rows reports errors / 上传含无效行的文件报告错误。"""
        csv = "name,ip,location\nswitch-01,192.168.1.1,A\n,invalid-ip,B\n"
        f = tmp_path / "bad.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("bad.csv", fh, "text/csv")})
        data = resp.json()
        assert data["total_rows"] == 2
        assert data["error_rows"] >= 1
        assert data["valid_rows"] < data["total_rows"]

    # -------------------------------------------------------------------
    # Unique constraint tests / 唯一约束测试
    # -------------------------------------------------------------------

    async def test_infile_duplicate_detected(self, client: AsyncClient, tmp_path: Path) -> None:
        """In-file duplicate names detected at upload / 文件内重复 name 在上传阶段被检测。"""
        csv = "name,ip,location\ndup-01,10.0.0.1,A\ndup-01,10.0.0.2,B\nunique-01,10.0.0.3,C\n"
        f = tmp_path / "dup.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("dup.csv", fh, "text/csv")})
        data = resp.json()
        assert data["total_rows"] == 3
        # Two rows have the same name -> at least 2 error rows (infile duplicate)
        # 两行 name 相同 -> 至少 2 个错误行（文件内重复）
        assert data["error_rows"] >= 2
        dup_errors = [e for e in data["errors"] if "duplicate" in e.get("message", "").lower()]
        assert len(dup_errors) >= 2

    async def test_db_conflict_on_commit(
        self,
        client: AsyncClient,
        csv_path: Path,
    ) -> None:
        """DB unique conflict returns 409 on second import / 第二次导入相同数据返回 409。"""
        # First import -> commit / 第一次导入并提交
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        commit1 = await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})
        assert commit1.status_code == 200

        # Second import with same data -> commit triggers conflict / 第二次导入触发冲突
        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        resp = await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})
        assert resp.status_code == 409
        body = resp.json()
        assert "message" in body
        assert "unique" in body["message"].lower() or "constraint" in body["message"].lower()

    async def test_db_conflict_preserves_original_data(
        self,
        client: AsyncClient,
        csv_path: Path,
        db_session: tuple[async_sessionmaker[AsyncSession], str],
    ) -> None:
        """After a conflict, original data remains intact / 冲突后原始数据保持不变。"""
        factory, _ = db_session
        # First import / 第一次导入
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        # Second import triggers conflict / 第二次导入触发冲突
        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})

        # DB still has exactly 5 records / 数据库仍然只有 5 条记录
        async with factory() as session:
            result = await session.execute(select(Device))
            devices = result.scalars().all()
            assert len(devices) == 5

    async def test_partial_duplicate_with_db(self, client: AsyncClient, csv_path: Path, tmp_path: Path) -> None:
        """File with mix of new and existing names -> conflict on commit / 新旧混合 -> 提交冲突。"""
        # First: import original data / 先导入原始数据
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        # Second: file with 1 existing name + 1 new name / 含 1 个已存在 + 1 个新 name
        csv = "name,ip,location\nswitch-01,10.0.0.99,New\nbrand-new-device,10.0.0.100,New\n"
        f = tmp_path / "partial_dup.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            d2 = (await client.post("/import/upload", files={"file": ("partial_dup.csv", fh, "text/csv")})).json()
        assert d2["total_rows"] == 2

        # Commit should fail (switch-01 exists) / 提交应失败（switch-01 已存在）
        resp = await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})
        assert resp.status_code == 409

    async def test_empty_name_no_constraint_trigger(self, client: AsyncClient, tmp_path: Path) -> None:
        """Empty name fails validation, not unique constraint / 空 name 走校验失败，非唯一约束。"""
        csv = "name,ip,location\n,10.0.0.1,A\n,10.0.0.2,B\n"
        f = tmp_path / "empty_names.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("empty_names.csv", fh, "text/csv")})
        data = resp.json()
        # Both rows fail validation (name blank) / 两行都校验失败（name 为空）
        assert data["error_rows"] == 2
        assert data["valid_rows"] == 0
        # Errors should be "required" type, not "duplicate" / 错误类型应为 required，非 duplicate
        for err in data["errors"]:
            assert "required" in err["message"].lower() or "必填" in err["message"]

    async def test_case_sensitivity_unique(
        self,
        client: AsyncClient,
        csv_path: Path,
        tmp_path: Path,
        db_session: tuple[async_sessionmaker[AsyncSession], str],
    ) -> None:
        """Case-different names are distinct in SQLite / SQLite 中大小写不同视为不同。"""
        factory, _ = db_session
        # Import original (lowercase: switch-01) / 导入原始数据
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        # Import SWITCH-01 (uppercase) / 导入大写 SWITCH-01
        csv = "name,ip,location\nSWITCH-01,10.0.0.99,Uppercase\n"
        f = tmp_path / "upper.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            d2 = (await client.post("/import/upload", files={"file": ("upper.csv", fh, "text/csv")})).json()
        resp = await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})
        # SQLite default: case-sensitive -> should succeed / SQLite 默认大小写敏感 -> 应成功
        assert resp.status_code == 200

        async with factory() as session:
            result = await session.execute(select(Device))
            devices = result.scalars().all()
            assert len(devices) == 6  # 5 original + 1 uppercase / 5 原始 + 1 大写

    async def test_triple_infile_duplicate(self, client: AsyncClient, tmp_path: Path) -> None:
        """3+ rows with same name all flagged as duplicates / 3 行以上同名全部标记为重复。"""
        csv = "name,ip,location\naaa,10.0.0.1,A\naaa,10.0.0.2,B\naaa,10.0.0.3,C\nbbb,10.0.0.4,D\n"
        f = tmp_path / "triple.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("triple.csv", fh, "text/csv")})
        data = resp.json()
        assert data["total_rows"] == 4
        # All 3 "aaa" rows should be errors / 3 行 aaa 都应为错误
        assert data["error_rows"] >= 3
        # Only "bbb" is valid / 只有 bbb 有效
        assert data["valid_rows"] == 1

    async def test_retry_success_with_unique_data(
        self,
        client: AsyncClient,
        csv_path: Path,
        tmp_path: Path,
        db_session: tuple[async_sessionmaker[AsyncSession], str],
    ) -> None:
        """After conflict, retry with unique data succeeds / 冲突后用不重复数据重试可成功。"""
        factory, _ = db_session
        # First import / 第一次导入
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        # Second: same data -> 409 / 相同数据 -> 409
        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        r2 = await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})
        assert r2.status_code == 409

        # Third: all-new data -> 200 / 全新数据 -> 200
        csv = "name,ip,location\nnew-dev-1,10.0.0.51,X\nnew-dev-2,10.0.0.52,Y\n"
        f = tmp_path / "new.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            d3 = (await client.post("/import/upload", files={"file": ("new.csv", fh, "text/csv")})).json()
        r3 = await client.post(f"/import/{d3['import_id']}/commit", params={"checksum": d3["checksum"]})
        assert r3.status_code == 200
        assert r3.json()["imported_rows"] == 2

        async with factory() as session:
            result = await session.execute(select(Device))
            assert len(result.scalars().all()) == 7  # 5 + 2

    async def test_export_intact_after_conflict(self, client: AsyncClient, csv_path: Path) -> None:
        """Export returns correct data even after a failed import / 失败导入后导出仍然正确。"""
        # Import and commit / 导入并提交
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        # Attempt duplicate -> 409 / 重复导入 -> 409
        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})

        # Export still works and contains original data / 导出仍正常且包含原始数据
        resp = await client.get("/export")
        assert resp.status_code == 200
        body = resp.text
        assert "switch-01" in body
        assert "firewall-01" in body

    async def test_infile_dup_plus_validation_error(self, client: AsyncClient, tmp_path: Path) -> None:
        """File with both duplicate names and invalid IPs / 文件同时含重复名和无效 IP。"""
        csv = "name,ip,location\ndup,10.0.0.1,A\ndup,invalid-ip,B\nok,10.0.0.3,C\n"
        f = tmp_path / "mixed.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("mixed.csv", fh, "text/csv")})
        data = resp.json()
        assert data["total_rows"] == 3
        # Row 2 has both a validation error (invalid IP) and a duplicate error
        # Row 1 has a duplicate error; only row 3 ("ok") should be valid
        # 第 1、2 行为重复，第 2 行同时 IP 无效，只有第 3 行有效
        assert data["error_rows"] >= 2
        assert data["valid_rows"] <= 1
        # Should have both duplicate and IP errors / 应同时含重复和 IP 错误
        messages = " ".join(e.get("message", "").lower() for e in data["errors"])
        assert "duplicate" in messages
        assert "ip" in messages or "无效" in messages
