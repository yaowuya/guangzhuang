"""SQLite 在线一致性备份、原子落盘和七份轮换测试。"""

from datetime import UTC, datetime, timedelta
import sqlite3

import pytest

from app.backup import daily_backup
from app.errors import ApiError
from app.schedule import tick


def test_consistent_backup_and_rotation(db, article_factory, tmp_path, now):
    """连续九天在线备份只保留最近七份，最新快照完整且含已提交标题。"""
    article_factory()
    folder = tmp_path / "backups"
    path = db.bind.url.database
    for day in range(9):
        daily_backup(path, folder, now + timedelta(days=day))
    files = sorted(folder.glob("backup-*.sqlite3"))
    assert len(files) == 7
    with sqlite3.connect(files[-1]) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
        assert restored.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0004_sessions"


def test_daily_backup_is_idempotent_and_uses_shanghai_date(db, article_factory, tmp_path):
    """同一北京时间日期已有有效文件时不重写，UTC跨日按上海日期命名。"""
    article_factory()
    folder = tmp_path / "backups"
    utc = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)  # 上海次日07:30
    created = daily_backup(db.bind.url.database, folder, utc)
    assert created.name == "backup-2026-01-02.sqlite3"
    mtime = created.stat().st_mtime_ns
    assert daily_backup(db.bind.url.database, folder, utc + timedelta(minutes=1)) is None
    assert created.stat().st_mtime_ns == mtime


def test_backup_failure_preserves_last_valid_and_cleans_temporary(
    db, article_factory, tmp_path, now, monkeypatch,
):
    """新快照写失败不先删旧备份，也不留下可误认的临时文件。"""
    from app import backup

    article_factory()
    folder = tmp_path / "backups"
    previous = daily_backup(db.bind.url.database, folder, now)

    def disk_full(source, temporary):
        temporary.write_bytes(b"partial")
        raise OSError("DISK_FULL_SENTINEL")

    monkeypatch.setattr(backup, "_online_backup", disk_full)
    with pytest.raises(ApiError) as error:
        daily_backup(db.bind.url.database, folder, now + timedelta(days=1))
    assert error.value.code == "backup_failed"
    assert previous.exists()
    assert not list(folder.glob("*.tmp"))
    assert not list(folder.glob(".*.tmp"))


def test_missing_or_unmigrated_database_never_becomes_backup(tmp_path, now):
    """不存在或无七表/迁移版本的SQLite文件不能获得正式backup文件名。"""
    folder = tmp_path / "backups"
    with pytest.raises(ApiError):
        daily_backup(tmp_path / "missing.sqlite3", folder, now)
    empty = tmp_path / "empty.sqlite3"
    connection = sqlite3.connect(empty)
    connection.close()
    with pytest.raises(ApiError):
        daily_backup(empty, folder, now)
    assert list(folder.glob("backup-*.sqlite3")) == []


def test_idle_tick_creates_backup_and_failure_is_safe_retryable(
    db, article_factory, tmp_path, caplog, monkeypatch,
):
    """空闲维护创建备份；次日失败只写安全事件并保留上一份。"""
    from app import schedule

    article_factory()
    folder = tmp_path / "backups"
    db.info["backup_dir"] = folder
    before_schedule = datetime(2026, 1, 1, 22, 0, tzinfo=UTC)  # 上海06:00
    assert tick(db, before_schedule) is None
    previous = folder / "backup-2026-01-02.sqlite3"
    assert previous.exists()

    def fail_backup(*args, **kwargs):
        raise ApiError("backup_failed", "DISK_FULL_SENTINEL", 503)

    monkeypatch.setattr(schedule, "daily_backup", fail_backup)
    assert tick(db, before_schedule + timedelta(days=1)) is None
    assert previous.exists()
    assert any(record.message == "backup_failed" for record in caplog.records)
    assert "DISK_FULL_SENTINEL" not in caplog.text
