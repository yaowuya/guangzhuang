"""SQLite 在线一致性备份、完整性校验、原子替换与七份轮换。"""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
