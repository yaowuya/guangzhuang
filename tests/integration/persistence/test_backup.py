"""SQLite 在线一致性备份、原子落盘和七份轮换测试。"""

from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from app.infrastructure.persistence.backup import backup_once, daily_backup, main, restore_backup
from app.infrastructure.persistence.database import application_lease
from app.core.exceptions import ApiError
from app.application.scheduling import tick


def test_backup_create_cli_uses_online_snapshot(db, article_factory, tmp_path, capsys):
    """部署工具可创建一致性备份，不需要复制正在运行的 SQLite 文件。"""
    article_factory(title="CLI备份标题")
    folder = tmp_path / "cli-backups"
    assert main([
        "create", "--database", db.bind.url.database, "--directory", str(folder),
    ]) == 0
    output = capsys.readouterr().out.strip()
    created = Path(output.removeprefix("backup="))
    assert created.is_file()
    with closing(sqlite3.connect(created)) as snapshot:
        assert snapshot.execute("SELECT title FROM articles").fetchone()[0] == "CLI备份标题"


def test_consistent_backup_and_rotation(db, article_factory, tmp_path, now):
    """连续九天在线备份只保留最近七份，最新快照完整且含已提交标题。"""
    article_factory()
    folder = tmp_path / "backups"
    path = db.bind.url.database
    for day in range(9):
        daily_backup(path, folder, now + timedelta(days=day))
    files = sorted(folder.glob("backup-*.sqlite3"))
    assert len(files) == 7
    with closing(sqlite3.connect(files[-1])) as restored:
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
    from app.infrastructure.persistence import backup

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


def test_existing_daily_backup_rotation_error_is_safe(db, article_factory, tmp_path, now, monkeypatch):
    """已有当日健康快照时，旧份轮换失败也转换为可重试backup_failed。"""
    article_factory()
    folder = tmp_path / "backups"
    current = daily_backup(db.bind.url.database, folder, now)
    for day in range(1, 8):
        shutil.copyfile(current, folder / f"backup-2025-12-{day:02d}.sqlite3")
    obsolete = folder / "backup-2025-12-01.sqlite3"
    real_unlink = type(obsolete).unlink

    def deny_obsolete(path, *args, **kwargs):
        if path == obsolete:
            raise PermissionError("ROTATION_DENIED_SENTINEL")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(type(obsolete), "unlink", deny_obsolete)
    with pytest.raises(ApiError) as error:
        daily_backup(db.bind.url.database, folder, now)
    assert (error.value.status, error.value.code) == (503, "backup_failed")
    assert current.exists() and obsolete.exists()


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
    from app.application import scheduling as schedule

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


def test_idle_tick_validates_daily_backup_once_per_worker_day(db, tmp_path, monkeypatch):
    """空闲worker同一天只做一次完整备份校验，失败时才保留下次tick重试。"""
    from app.application import scheduling as schedule

    calls = []
    db.info["backup_dir"] = tmp_path / "backups"

    def record_backup(db_path, directory, now):
        calls.append((db_path, directory, now.date()))
        return None

    monkeypatch.setattr(schedule, "daily_backup", record_backup)
    first = datetime(2026, 1, 1, 22, 0, tzinfo=UTC)
    assert tick(db, first) is None
    assert tick(db, first + timedelta(seconds=1)) is None
    assert len(calls) == 1
    assert tick(db, first + timedelta(days=1)) is None
    assert len(calls) == 2


def test_restore_requires_stop_and_confirmation(db, article_factory, tmp_path, now):
    """确认文本不能替代实际停服务，共享lease存在时独占恢复被拒绝。"""
    article_factory()
    image = backup_once(db.bind.url.database, tmp_path / "backups", now)
    lease = tmp_path / "application.lock"
    with pytest.raises(ValueError):
        restore_backup(image, db.bind.url.database, lease, "")
    with application_lease(lease):
        with pytest.raises(RuntimeError, match="仍在运行"):
            restore_backup(image, db.bind.url.database, lease, "已确认损失备份后的写入")


def test_restore_roundtrip_preserves_pre_restore_and_recovers_business_data(
    db, article_factory, tmp_path, now,
):
    """恢复前保存当前较新状态，恢复后标题/收藏/任务表可重新打开读取。"""
    from app.infrastructure.persistence.models import Bookmark

    article = article_factory(title="备份中的标题")
    db.add(Bookmark(article_id=article.id, created_at=now))
    db.commit()
    database = db.bind.url.database
    image = backup_once(database, tmp_path / "backups", now)

    article.title = "备份后的新写入"
    db.delete(db.get(Bookmark, article.id))
    db.commit()
    engine = db.bind
    db.close()
    engine.dispose()

    pre_restore = restore_backup(
        image, database, tmp_path / "application.lock", "已确认损失备份后的写入",
    )
    with closing(sqlite3.connect(database)) as restored:
        assert restored.execute("SELECT title FROM articles WHERE id=?", (article.id,)).fetchone()[0] == "备份中的标题"
        assert restored.execute("SELECT COUNT(*) FROM bookmarks WHERE article_id=?", (article.id,)).fetchone()[0] == 1
        assert restored.execute("SELECT COUNT(*) FROM update_jobs").fetchone()[0] == 0
    with closing(sqlite3.connect(pre_restore)) as previous:
        assert previous.execute("SELECT title FROM articles WHERE id=?", (article.id,)).fetchone()[0] == "备份后的新写入"
        assert previous.execute("SELECT COUNT(*) FROM bookmarks WHERE article_id=?", (article.id,)).fetchone()[0] == 0


def test_valid_backup_recovers_corrupt_current_database_and_preserves_forensics(
    db, article_factory, tmp_path, now,
):
    """运行库损坏时仍可恢复，并原样保留损坏主文件与sidecar供取证。"""
    article_factory(title="可恢复标题")
    database = Path(db.bind.url.database)
    image = backup_once(database, tmp_path / "backups", now)
    engine = db.bind
    db.close()
    engine.dispose()

    database.write_bytes(b"CORRUPT_CURRENT_SENTINEL")
    Path(f"{database}-wal").write_bytes(b"CORRUPT_WAL_SENTINEL")
    pre_restore = restore_backup(
        image, database, tmp_path / "application.lock", "已确认损失备份后的写入",
    )
    assert pre_restore is not None
    assert pre_restore.read_bytes() == b"CORRUPT_CURRENT_SENTINEL"
    assert Path(f"{pre_restore}-wal").read_bytes() == b"CORRUPT_WAL_SENTINEL"
    with closing(sqlite3.connect(database)) as restored:
        assert restored.execute("SELECT title FROM articles").fetchone()[0] == "可恢复标题"


def test_valid_backup_recovers_missing_current_database(db, article_factory, tmp_path, now):
    """整库文件缺失时直接安装已验证备份，并如实返回没有pre-restore。"""
    article_factory(title="缺库恢复标题")
    database = Path(db.bind.url.database)
    image = backup_once(database, tmp_path / "backups", now)
    engine = db.bind
    db.close()
    engine.dispose()
    database.unlink()

    pre_restore = restore_backup(
        image, database, tmp_path / "application.lock", "已确认损失备份后的写入",
    )
    assert pre_restore is None
    with closing(sqlite3.connect(database)) as restored:
        assert restored.execute("SELECT title FROM articles").fetchone()[0] == "缺库恢复标题"


def test_corrupt_restore_input_leaves_current_database_unchanged(db, article_factory, tmp_path, now):
    """坏备份在取得写锁和pre-restore之前拒绝，运行库原数据保持。"""
    article = article_factory(title="当前有效标题")
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not sqlite")
    with pytest.raises(ValueError):
        restore_backup(corrupt, db.bind.url.database, tmp_path / "application.lock",
                       "已确认损失备份后的写入")
    db.expire_all()
    assert db.get(type(article), article.id).title == "当前有效标题"
    assert not (tmp_path / "pre-restore").exists()


def test_restore_rejects_wrong_revision_missing_columns_and_orphan_foreign_keys(
    db, article_factory, tmp_path, now,
):
    """伪造表名、未知迁移版本和孤儿引用都不能替换当前运行库。"""
    article_factory()
    valid = backup_once(db.bind.url.database, tmp_path / "backups", now)
    candidates = []

    wrong_revision = tmp_path / "wrong-revision.sqlite3"
    shutil.copyfile(valid, wrong_revision)
    with closing(sqlite3.connect(wrong_revision)) as connection:
        connection.execute("UPDATE alembic_version SET version_num='future_or_fake'")
        connection.commit()
    candidates.append(wrong_revision)

    missing_columns = tmp_path / "missing-columns.sqlite3"
    with closing(sqlite3.connect(missing_columns)) as connection:
        connection.execute("CREATE TABLE alembic_version(version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('0004_sessions')")
        for table in ("sources", "source_entries", "articles", "bookmarks",
                      "update_jobs", "entry_results", "sessions"):
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
        connection.commit()
    candidates.append(missing_columns)

    orphan = tmp_path / "orphan.sqlite3"
    shutil.copyfile(valid, orphan)
    with closing(sqlite3.connect(orphan)) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO bookmarks(article_id,created_at) VALUES (999999,'2026-01-01T00:00:00')"
        )
        connection.commit()
    candidates.append(orphan)

    wrong_index = tmp_path / "wrong-index.sqlite3"
    shutil.copyfile(valid, wrong_index)
    with closing(sqlite3.connect(wrong_index)) as connection:
        connection.execute("DROP INDEX uq_active_job")
        connection.execute("CREATE UNIQUE INDEX uq_active_job ON update_jobs(active_key)")
        connection.commit()
    candidates.append(wrong_index)

    wrong_check = tmp_path / "wrong-check.sqlite3"
    shutil.copyfile(valid, wrong_check)
    with closing(sqlite3.connect(wrong_check)) as connection:
        original_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='update_jobs'"
        ).fetchone()[0]
        weakened_sql = original_sql.replace(
            "CONSTRAINT ck_job_state CHECK (state IN ('pending','running','succeeded','partial','failed','interrupted'))",
            "CONSTRAINT ck_job_state CHECK (1)",
        )
        assert weakened_sql != original_sql
        version = connection.execute("PRAGMA schema_version").fetchone()[0]
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name='update_jobs'",
                           (weakened_sql,))
        connection.execute("PRAGMA writable_schema=OFF")
        connection.execute(f"PRAGMA schema_version={version + 1}")
        connection.commit()
    candidates.append(wrong_check)

    for candidate in candidates:
        with pytest.raises(ValueError):
            restore_backup(candidate, db.bind.url.database, tmp_path / "application.lock",
                           "已确认损失备份后的写入")
    assert not (tmp_path / "pre-restore").exists()


def test_restore_replace_failure_preserves_committed_wal_data(
    db, article_factory, tmp_path, now, monkeypatch,
):
    """安装staged失败前先checkpoint，当前库不能因sidecar清理丢失已提交WAL写入。"""
    from app.infrastructure.persistence import backup

    article = article_factory(title="备份版本")
    database = db.bind.url.database
    image = backup_once(database, tmp_path / "backups", now)
    article_id = article.id
    engine = db.bind
    db.close()
    engine.dispose()

    script = """
import os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1])
connection.execute('PRAGMA journal_mode=WAL')
connection.execute('PRAGMA wal_autocheckpoint=0')
connection.execute('UPDATE articles SET title=? WHERE id=?', ('WAL最新写入', int(sys.argv[2])))
connection.commit()
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", script, database, str(article_id)], check=True)
    assert Path(f"{database}-wal").exists()
    real_replace = backup.os.replace

    def fail_install(source, target):
        if Path(target) == Path(database) and str(source).endswith(".restore"):
            raise OSError("REPLACE_FAILED_SENTINEL")
        return real_replace(source, target)

    monkeypatch.setattr(backup.os, "replace", fail_install)
    with pytest.raises(ApiError) as error:
        restore_backup(image, database, tmp_path / "application.lock",
                       "已确认损失备份后的写入")
    assert error.value.code == "restore_failed"
    with closing(sqlite3.connect(database)) as current:
        assert current.execute("SELECT title FROM articles WHERE id=?", (article_id,)).fetchone()[0] == "WAL最新写入"


def test_api_lifespan_holds_shared_application_lease(client, db, article_factory, settings, tmp_path, now):
    """TestClient生命周期模拟API进程；其共享lease阻止离线恢复覆盖运行库。"""
    article_factory()
    image = backup_once(db.bind.url.database, tmp_path / "backups", now)
    with pytest.raises(RuntimeError, match="仍在运行"):
        restore_backup(
            image, db.bind.url.database, settings.data_dir / "application.lock",
            "已确认损失备份后的写入",
        )
    assert client.get("/api/articles").status_code == 401
