"""SQLite 在线一致性备份、完整性校验、原子替换与七份轮换。"""

import argparse
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .database import application_lease
from .errors import ApiError

_EXPECTED_TABLES = {
    "sources", "source_entries", "articles", "bookmarks",
    "update_jobs", "entry_results", "sessions",
}
_BACKUP_NAME = re.compile(r"backup-(\d{4}-\d{2}-\d{2})\.sqlite3\Z")
try:
    _SHANGHAI = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    _SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _day(now: datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ApiError("backup_failed", "备份时间必须包含时区", 503)
    return now.astimezone(_SHANGHAI).date()


def _validate_database(path: Path) -> None:
    """确认快照完整并包含七张业务表及非空迁移版本。"""
    if not path.is_file():
        raise ApiError("backup_failed", "备份数据库不存在", 503)
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            checks = [row[0] for row in connection.execute("PRAGMA integrity_check")]
            if checks != ["ok"]:
                raise ApiError("backup_failed", "备份完整性检查失败", 503)
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if not _EXPECTED_TABLES <= tables or "alembic_version" not in tables:
                raise ApiError("backup_failed", "数据库迁移结构不完整", 503)
            version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            if version is None or not isinstance(version[0], str) or not version[0]:
                raise ApiError("backup_failed", "数据库迁移版本无效", 503)
    except ApiError:
        raise
    except sqlite3.Error:
        raise ApiError("backup_failed", "备份数据库不可读取", 503) from None


def _online_backup(source_path: Path, temporary: Path) -> None:
    """使用 SQLite backup API 读取运行库，不以文件复制替代一致性快照。"""
    with closing(sqlite3.connect(str(source_path))) as source, closing(sqlite3.connect(str(temporary))) as destination:
        source.backup(destination)


def _rotate(directory: Path) -> None:
    files = sorted(
        path for path in directory.iterdir()
        if path.is_file() and _BACKUP_NAME.fullmatch(path.name)
    )
    for obsolete in files[:-7]:
        obsolete.unlink()


def backup_once(db_path: str | Path, directory: str | Path, now: datetime) -> Path:
    """生成校验通过的在线快照；原子落盘成功后才轮换旧备份。"""
    source = Path(db_path)
    folder = Path(directory)
    target = folder / f"backup-{_day(now).isoformat()}.sqlite3"
    temporary = folder / f".{target.name}.{uuid4().hex}.tmp"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        _validate_database(source)
        _online_backup(source, temporary)
        _validate_database(temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        _rotate(folder)
        return target
    except ApiError:
        raise
    except (OSError, sqlite3.Error):
        raise ApiError("backup_failed", "备份写入失败", 503) from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            # 不让临时文件清理失败覆盖稳定backup_failed；后续维护可按隐藏.tmp清理。
            pass


def daily_backup(db_path: str | Path, directory: str | Path, now: datetime) -> Path | None:
    """当日有效备份只保留一份；失败不会删除最后可用快照，下次tick可重试。"""
    folder = Path(directory)
    target = folder / f"backup-{_day(now).isoformat()}.sqlite3"
    if target.exists():
        try:
            _validate_database(target)
            _rotate(folder)
            return None
        except ApiError:
            # 当日文件损坏时保留到新快照完成原子替换为止。
            pass
    return backup_once(db_path, folder, now)


_RESTORE_CONFIRMATION = "已确认损失备份后的写入"


def _assert_database_offline(path: Path) -> None:
    """除文件lease外再取得SQLite EXCLUSIVE，拒绝未遵守lease的活动连接。"""
    try:
        with closing(sqlite3.connect(str(path), timeout=0, isolation_level=None)) as connection:
            connection.execute("BEGIN EXCLUSIVE")
            connection.execute("ROLLBACK")
    except sqlite3.Error:
        raise RuntimeError("API或worker仍在运行，数据库未停写") from None


def _snapshot_to(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        _validate_database(source)
        _online_backup(source, temporary)
        _validate_database(temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def restore_backup(
    backup_path: str | Path,
    db_path: str | Path,
    lease_path: str | Path,
    confirmation: str,
) -> Path:
    """独占停写后恢复已验证快照，并先保存当前运行库为pre-restore安全副本。"""
    if confirmation.strip() != _RESTORE_CONFIRMATION:
        raise ValueError("必须明确确认备份后的写入会丢失")
    backup = Path(backup_path).resolve()
    database = Path(db_path).resolve()
    if backup == database:
        raise ValueError("备份文件不能与运行数据库相同")
    try:
        _validate_database(backup)
    except ApiError:
        raise ValueError("备份文件损坏或结构不完整") from None
    try:
        lease = application_lease(lease_path, exclusive=True)
        with lease:
            _validate_database(database)
            _assert_database_offline(database)
            pre_directory = database.parent / "pre-restore"
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            pre_restore = pre_directory / f"pre-restore-{stamp}-{uuid4().hex}.sqlite3"
            _snapshot_to(database, pre_restore)

            staged = database.with_name(f".{database.name}.{uuid4().hex}.restore")
            try:
                _online_backup(backup, staged)
                _validate_database(staged)
                os.chmod(staged, 0o600)
                for suffix in ("-wal", "-shm", "-journal"):
                    Path(f"{database}{suffix}").unlink(missing_ok=True)
                os.replace(staged, database)
                _validate_database(database)
            finally:
                try:
                    staged.unlink(missing_ok=True)
                except OSError:
                    pass
            return pre_restore
    except RuntimeError:
        raise RuntimeError("API或worker仍在运行，必须先停服务") from None
    except ApiError:
        raise
    except (OSError, sqlite3.Error):
        raise ApiError("restore_failed", "数据库恢复失败", 503) from None


def main(argv: list[str] | None = None) -> int:
    """离线恢复CLI；命令本身不停止服务，也不会把恢复当作发布成功。"""
    parser = argparse.ArgumentParser(prog="python -m app.backup")
    subcommands = parser.add_subparsers(dest="command", required=True)
    restore = subcommands.add_parser("restore")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--database", required=True)
    restore.add_argument("--lease", required=True)
    restore.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    if args.command == "restore":
        pre_restore = restore_backup(
            args.backup, args.database, args.lease, args.confirm,
        )
        print(f"pre_restore={pre_restore}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
