"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_e2e.py
@DateTime: 2026-02-08
@Docs: End-to-end tests for Tortoise ORM example app.
Tortoise ORM 示例应用的端到端测试。
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from .models import Device


@pytest.mark.asyncio
class TestTortoiseE2E:
    """Tortoise ORM end-to-end import/export tests.
    Tortoise ORM 端到端导入导出测试。
    """

    async def test_upload_csv(self, client: AsyncClient, csv_path: Path) -> None:
        with open(csv_path, "rb") as f:
            resp = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 5
        assert data["valid_rows"] == 5
        assert data["error_rows"] == 0

    async def test_upload_xlsx(self, client: AsyncClient, xlsx_path: Path) -> None:
        with open(xlsx_path, "rb") as f:
            resp = await client.post(
                "/import/upload",
                files={"file": ("devices.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        assert resp.status_code == 200
        assert resp.json()["total_rows"] == 5

    async def test_preview_all(self, client: AsyncClient, csv_path: Path) -> None:
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()
        resp = await client.get(
            f"/import/{data['import_id']}/preview",
            params={"checksum": data["checksum"], "kind": "all"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_rows"] == 5
        assert len(resp.json()["rows"]) == 5

    async def test_preview_valid(self, client: AsyncClient, csv_path: Path) -> None:
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
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()
        resp = await client.post(
            f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]},
        )
        assert resp.status_code == 200
        commit = resp.json()
        assert commit["status"] == "committed"
        assert commit["imported_rows"] == 5

    async def test_commit_verifies_database(self, client: AsyncClient, csv_path: Path) -> None:
        """After commit, database has 5 Device records / 提交后数据库有 5 条设备记录。"""
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()
        await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})

        devices = await Device.all()
        assert len(devices) == 5
        names = {d.name for d in devices}
        assert "switch-01" in names
        assert "firewall-01" in names

    async def test_export_after_commit(self, client: AsyncClient, csv_path: Path) -> None:
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()
        await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})

        resp = await client.get("/export")
        assert resp.status_code == 200
        assert "switch-01" in resp.text

    async def test_commit_idempotent(self, client: AsyncClient, csv_path: Path) -> None:
        with open(csv_path, "rb") as f:
            upload = await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})
        data = upload.json()
        await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})
        resp2 = await client.post(f"/import/{data['import_id']}/commit", params={"checksum": data["checksum"]})
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "committed"

    async def test_upload_with_validation_errors(self, client: AsyncClient, tmp_path: Path) -> None:
        csv = "name,ip,location\nswitch-01,192.168.1.1,A\n,invalid-ip,B\n"
        f = tmp_path / "bad.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("bad.csv", fh, "text/csv")})
        data = resp.json()
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
        assert data["error_rows"] >= 2
        dup_errors = [e for e in data["errors"] if "duplicate" in e.get("message", "").lower()]
        assert len(dup_errors) >= 2

    async def test_db_conflict_on_commit(self, client: AsyncClient, csv_path: Path) -> None:
        """DB unique conflict returns 409 on second import / 第二次导入返回 409。"""
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        resp = await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})
        assert resp.status_code == 409
        assert "unique" in resp.json()["message"].lower() or "constraint" in resp.json()["message"].lower()

    async def test_db_conflict_preserves_original_data(self, client: AsyncClient, csv_path: Path) -> None:
        """After a conflict, original data remains intact / 冲突后原始数据不变。"""
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})

        devices = await Device.all()
        assert len(devices) == 5

    async def test_partial_duplicate_with_db(self, client: AsyncClient, csv_path: Path, tmp_path: Path) -> None:
        """Mix of new + existing names -> conflict / 新旧混合 -> 冲突。"""
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        csv = "name,ip,location\nswitch-01,10.0.0.99,New\nbrand-new,10.0.0.100,New\n"
        f = tmp_path / "partial.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            d2 = (await client.post("/import/upload", files={"file": ("partial.csv", fh, "text/csv")})).json()
        resp = await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})
        assert resp.status_code == 409

    async def test_empty_name_validation_not_constraint(self, client: AsyncClient, tmp_path: Path) -> None:
        """Empty names fail validation, not constraint / 空 name 走校验失败。"""
        csv = "name,ip,location\n,10.0.0.1,A\n,10.0.0.2,B\n"
        f = tmp_path / "empty.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("empty.csv", fh, "text/csv")})
        data = resp.json()
        assert data["error_rows"] == 2
        assert data["valid_rows"] == 0

    async def test_case_sensitivity_unique(self, client: AsyncClient, csv_path: Path, tmp_path: Path) -> None:
        """Case-different names are distinct / 大小写不同视为不同。"""
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        csv = "name,ip,location\nSWITCH-01,10.0.0.99,Upper\n"
        f = tmp_path / "upper.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            d2 = (await client.post("/import/upload", files={"file": ("upper.csv", fh, "text/csv")})).json()
        resp = await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})
        assert resp.status_code == 200

        devices = await Device.all()
        assert len(devices) == 6

    async def test_triple_infile_duplicate(self, client: AsyncClient, tmp_path: Path) -> None:
        """3+ rows with same name all flagged / 3 行以上同名全标为重复。"""
        csv = "name,ip,location\naaa,10.0.0.1,A\naaa,10.0.0.2,B\naaa,10.0.0.3,C\nbbb,10.0.0.4,D\n"
        f = tmp_path / "triple.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("triple.csv", fh, "text/csv")})
        data = resp.json()
        assert data["total_rows"] == 4
        assert data["error_rows"] >= 3
        assert data["valid_rows"] == 1

    async def test_retry_success_with_unique_data(self, client: AsyncClient, csv_path: Path, tmp_path: Path) -> None:
        """After conflict, retry with unique data succeeds / 冲突后用不重复数据重试成功。"""
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        assert (await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})).status_code == 409

        csv = "name,ip,location\nnew-dev-1,10.0.0.51,X\nnew-dev-2,10.0.0.52,Y\n"
        f = tmp_path / "new.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            d3 = (await client.post("/import/upload", files={"file": ("new.csv", fh, "text/csv")})).json()
        r3 = await client.post(f"/import/{d3['import_id']}/commit", params={"checksum": d3["checksum"]})
        assert r3.status_code == 200
        assert r3.json()["imported_rows"] == 2

        devices = await Device.all()
        assert len(devices) == 7

    async def test_export_intact_after_conflict(self, client: AsyncClient, csv_path: Path) -> None:
        """Export still correct after failed import / 失败导入后导出仍正确。"""
        with open(csv_path, "rb") as f:
            d1 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d1['import_id']}/commit", params={"checksum": d1["checksum"]})

        with open(csv_path, "rb") as f:
            d2 = (await client.post("/import/upload", files={"file": ("devices.csv", f, "text/csv")})).json()
        await client.post(f"/import/{d2['import_id']}/commit", params={"checksum": d2["checksum"]})

        resp = await client.get("/export")
        assert resp.status_code == 200
        assert "switch-01" in resp.text
        assert "firewall-01" in resp.text

    async def test_infile_dup_plus_validation_error(self, client: AsyncClient, tmp_path: Path) -> None:
        """File with duplicate names + invalid IPs / 同时含重复名和无效 IP。"""
        csv = "name,ip,location\ndup,10.0.0.1,A\ndup,invalid-ip,B\nok,10.0.0.3,C\n"
        f = tmp_path / "mixed.csv"
        f.write_text(csv, encoding="utf-8")
        with open(f, "rb") as fh:
            resp = await client.post("/import/upload", files={"file": ("mixed.csv", fh, "text/csv")})
        data = resp.json()
        assert data["total_rows"] == 3
        assert data["error_rows"] >= 2
        assert data["valid_rows"] <= 1
        messages = " ".join(e.get("message", "").lower() for e in data["errors"])
        assert "duplicate" in messages
        assert "ip" in messages or "无效" in messages
