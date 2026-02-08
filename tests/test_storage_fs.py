"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_storage_fs.py
@DateTime: 2026-02-08
@Docs: Tests for storage_fs.py module.
storage_fs.py 模块测试。
"""

from pathlib import Path
from uuid import UUID

from fastapi_import_export.config import ImportExportConfig
from fastapi_import_export.storage_fs import (
    cleanup_expired_imports,
    create_export_path,
    delete_export_file,
    ensure_dirs,
    get_import_paths,
    new_import_id,
    now_ts,
    read_meta,
    safe_rmtree,
    safe_unlink,
    sha256_file,
    write_meta,
)


class TestNewImportId:
    """Tests for new_import_id.
    new_import_id 测试。
    """

    def test_returns_uuid(self) -> None:
        result = new_import_id()
        assert isinstance(result, UUID)

    def test_unique(self) -> None:
        """Two calls return different IDs / 两次调用返回不同 ID。"""
        a = new_import_id()
        b = new_import_id()
        assert a != b


class TestNowTs:
    """Tests for now_ts.
    now_ts 测试。
    """

    def test_returns_int(self) -> None:
        ts = now_ts()
        assert isinstance(ts, int)

    def test_reasonable_value(self) -> None:
        ts = now_ts()
        # Should be after 2020 and before 2100 / 应该在 2020-2100 之间
        assert ts > 1577836800
        assert ts < 4102444800


class TestEnsureDirs:
    """Tests for ensure_dirs.
    ensure_dirs 测试。
    """

    def test_creates_dirs(self, tmp_config: ImportExportConfig) -> None:
        ensure_dirs(config=tmp_config)
        assert tmp_config.imports_dir.exists()
        assert tmp_config.exports_dir.exists()

    def test_idempotent(self, tmp_config: ImportExportConfig) -> None:
        """Calling twice doesn't raise / 重复调用不报错。"""
        ensure_dirs(config=tmp_config)
        ensure_dirs(config=tmp_config)


class TestGetImportPaths:
    """Tests for get_import_paths.
    get_import_paths 测试。
    """

    def test_paths_correct(self, tmp_config: ImportExportConfig) -> None:
        uid = new_import_id()
        paths = get_import_paths(uid, config=tmp_config)
        assert paths.root == tmp_config.imports_dir / str(uid)
        assert paths.original == paths.root / "original"
        assert paths.meta == paths.root / "meta.json"
        assert paths.parsed_parquet == paths.root / "parsed.parquet"
        assert paths.errors_json == paths.root / "errors.json"
        assert paths.valid_parquet == paths.root / "valid.parquet"

    def test_base_dir_fallback(self, tmp_path: Path) -> None:
        uid = new_import_id()
        paths = get_import_paths(uid, base_dir=tmp_path)
        assert str(tmp_path) in str(paths.root)


class TestWriteReadMeta:
    """Tests for write_meta and read_meta.
    write_meta 与 read_meta 测试。
    """

    def test_roundtrip(self, tmp_config: ImportExportConfig) -> None:
        """Write then read returns same data / 写入后读取返回相同数据。"""
        uid = new_import_id()
        paths = get_import_paths(uid, config=tmp_config)
        meta = {"import_id": str(uid), "status": "uploaded", "filename": "test.csv"}
        write_meta(paths, meta)
        loaded = read_meta(paths)
        assert loaded == meta


class TestSha256File:
    """Tests for sha256_file.
    sha256_file 测试。
    """

    def test_known_content(self, tmp_path: Path) -> None:
        """Known content produces known hash / 已知内容产生已知 hash。"""
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        result = sha256_file(f)
        # sha256 of "hello"
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


class TestSafeUnlink:
    """Tests for safe_unlink.
    safe_unlink 测试。
    """

    def test_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("data")
        safe_unlink(f)
        assert not f.exists()

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """No error when file doesn't exist / 文件不存在时不报错。"""
        safe_unlink(tmp_path / "nonexistent.txt")


class TestSafeRmtree:
    """Tests for safe_rmtree.
    safe_rmtree 测试。
    """

    def test_existing_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "subdir"
        d.mkdir()
        (d / "file.txt").write_text("data")
        safe_rmtree(d)
        assert not d.exists()

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        """No error when dir doesn't exist / 目录不存在时不报错。"""
        safe_rmtree(tmp_path / "nonexistent_dir")


class TestDeleteExportFile:
    """Tests for delete_export_file.
    delete_export_file 测试。
    """

    def test_deletes_file(self, tmp_path: Path) -> None:
        f = tmp_path / "export.csv"
        f.write_text("data")
        delete_export_file(str(f))
        assert not f.exists()


class TestCreateExportPath:
    """Tests for create_export_path.
    create_export_path 测试。
    """

    def test_normal_filename(self, tmp_config: ImportExportConfig) -> None:
        path = create_export_path("report.csv", config=tmp_config)
        assert path.name == "report.csv"
        assert path.parent == tmp_config.exports_dir

    def test_path_traversal_defense(self, tmp_config: ImportExportConfig) -> None:
        """Path traversal is neutralized / 路径穿越被消除。"""
        path = create_export_path("../../etc/passwd", config=tmp_config)
        assert path.name == "passwd"
        assert path.parent == tmp_config.exports_dir

    def test_empty_filename_fallback(self, tmp_config: ImportExportConfig) -> None:
        """Empty filename falls back to 'export' / 空文件名回退到 'export'。"""
        path = create_export_path("", config=tmp_config)
        assert path.name == "export"


class TestCleanupExpiredImports:
    """Tests for cleanup_expired_imports.
    cleanup_expired_imports 测试。
    """

    def test_expired_cleaned(self, tmp_config: ImportExportConfig) -> None:
        """Expired dirs are cleaned / 过期目录被清理。"""
        ensure_dirs(config=tmp_config)
        uid = new_import_id()
        paths = get_import_paths(uid, config=tmp_config)
        meta = {"created_at": 1000000}  # Very old timestamp / 非常久远的时间戳
        write_meta(paths, meta)

        cleaned = cleanup_expired_imports(ttl_hours=1, config=tmp_config)
        assert cleaned == 1
        assert not paths.root.exists()

    def test_not_expired_preserved(self, tmp_config: ImportExportConfig) -> None:
        """Non-expired dirs preserved / 未过期目录保留。"""
        ensure_dirs(config=tmp_config)
        uid = new_import_id()
        paths = get_import_paths(uid, config=tmp_config)
        meta = {"created_at": now_ts()}
        write_meta(paths, meta)

        cleaned = cleanup_expired_imports(ttl_hours=1, config=tmp_config)
        assert cleaned == 0
        assert paths.root.exists()

    def test_corrupted_meta_still_cleaned(self, tmp_config: ImportExportConfig) -> None:
        """Dir with corrupted meta.json is still cleaned / meta.json 损坏的目录仍被清理。"""
        ensure_dirs(config=tmp_config)
        uid = new_import_id()
        job_dir = tmp_config.imports_dir / str(uid)
        job_dir.mkdir(parents=True)
        (job_dir / "meta.json").write_text("INVALID JSON!!!")

        cleaned = cleanup_expired_imports(ttl_hours=1, config=tmp_config)
        assert cleaned == 1

    def test_empty_imports_dir(self, tmp_config: ImportExportConfig) -> None:
        """Empty imports dir returns 0 / 空 imports 目录返回 0。"""
        ensure_dirs(config=tmp_config)
        cleaned = cleanup_expired_imports(ttl_hours=1, config=tmp_config)
        assert cleaned == 0

    def test_nonexistent_imports_dir(self, tmp_config: ImportExportConfig) -> None:
        """Nonexistent imports dir returns 0 / 不存在的 imports 目录返回 0。"""
        cleaned = cleanup_expired_imports(ttl_hours=1, config=tmp_config)
        assert cleaned == 0
