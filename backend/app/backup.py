"""SQLite 在线一致性备份、完整性校验、原子替换与七份轮换。"""

import argparse
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import create_engine

from .database import application_lease
from .errors import ApiError
from .models import Base

_EXPECTED_REVISION = "0004_sessions"
_EXPECTED_COLUMNS = {
    "sources": (("id", "INTEGER", 1, None, 1), ("key", "TEXT", 1, None, 0),
                ("name", "TEXT", 1, None, 0), ("language", "TEXT", 0, None, 0),
                ("verification_status", "TEXT", 1, "'pending'", 0),
                ("reason", "TEXT", 0, None, 0)),
    "source_entries": (("id", "INTEGER", 1, None, 1), ("source_id", "INTEGER", 1, None, 0),
                       ("url", "TEXT", 1, None, 0), ("kind", "TEXT", 1, None, 0),
                       ("verification_status", "TEXT", 1, "'pending'", 0),
                       ("verification_reason", "TEXT", 0, None, 0),
                       ("verification_reference", "TEXT", 0, None, 0),
                       ("enabled", "BOOLEAN", 1, "0", 0),
                       ("last_success_at", "DATETIME", 0, None, 0),
                       ("last_error", "TEXT", 0, None, 0)),
    "articles": (("id", "INTEGER", 1, None, 1), ("source_id", "INTEGER", 1, None, 0),
                 ("first_entry_id", "INTEGER", 1, None, 0),
                 ("original_url", "TEXT", 1, None, 0), ("dedup_url", "TEXT", 1, None, 0),
                 ("title", "TEXT", 1, None, 0), ("search_text", "TEXT", 1, None, 0),
                 ("reported_date", "DATE", 0, None, 0),
                 ("category_codes", "JSON", 1, "'[]'", 0),
                 ("region", "TEXT", 0, None, 0), ("product_type", "TEXT", 0, None, 0),
                 ("image_url", "TEXT", 0, None, 0), ("image_credit", "TEXT", 0, None, 0),
                 ("updated_at", "DATETIME", 1, None, 0)),
    "bookmarks": (("article_id", "INTEGER", 1, None, 1),
                  ("created_at", "DATETIME", 1, None, 0)),
    "update_jobs": (("id", "INTEGER", 1, None, 1), ("trigger", "TEXT", 1, None, 0),
                    ("state", "TEXT", 1, "'pending'", 0),
                    ("created_at", "DATETIME", 1, None, 0),
                    ("started_at", "DATETIME", 0, None, 0),
                    ("finished_at", "DATETIME", 0, None, 0),
                    ("schedule_date", "DATE", 0, None, 0),
                    ("active_key", "INTEGER", 1, "'1'", 0)),
    "entry_results": (("id", "INTEGER", 1, None, 1), ("job_id", "INTEGER", 1, None, 0),
                      ("entry_id", "INTEGER", 1, None, 0),
                      ("state", "TEXT", 1, "'pending'", 0),
                      ("count_added", "INTEGER", 1, "'0'", 0),
                      ("count_updated", "INTEGER", 1, "'0'", 0),
                      ("error", "TEXT", 0, None, 0),
                      ("finished_at", "DATETIME", 0, None, 0)),
    "sessions": (("id", "INTEGER", 1, None, 1), ("token_digest", "TEXT", 1, None, 0),
                 ("expires_at", "DATETIME", 1, None, 0),
                 ("created_at", "DATETIME", 1, None, 0)),
}
_EXPECTED_FOREIGN_KEYS = {
    "sources": set(),
    "source_entries": {("source_id", "sources", "id")},
    "articles": {("source_id", "sources", "id"), ("first_entry_id", "source_entries", "id")},
    "bookmarks": {("article_id", "articles", "id")},
    "update_jobs": set(),
    "entry_results": {("job_id", "update_jobs", "id"), ("entry_id", "source_entries", "id")},
    "sessions": set(),
}
_EXPECTED_UNIQUE_COLUMNS = {
    "sources": {("key",)},
    "source_entries": {("source_id", "url")},
    "articles": {("dedup_url",)},
    "bookmarks": set(),
    "update_jobs": set(),
    "entry_results": {("job_id", "entry_id")},
    "sessions": {("token_digest",)},
}
_EXPECTED_INDEX_SQL = {
    "ix_article_reported_id": "create index ix_article_reported_id on articles (reported_date desc, id desc)",
    "ix_bookmark_created": "create index ix_bookmark_created on bookmarks (created_at desc, article_id desc)",
    "ix_sessions_expires_at": "create index ix_sessions_expires_at on sessions (expires_at)",
    "uq_active_job": "create unique index uq_active_job on update_jobs (active_key) where state in ('pending','running')",
    "uq_daily_schedule": "create unique index uq_daily_schedule on update_jobs (schedule_date) where trigger='schedule'",
    "uq_daily_catchup": "create unique index uq_daily_catchup on update_jobs (schedule_date) where trigger='catchup'",
}
_EXPECTED_CONSTRAINT_NAMES = {
    "sources": {"uq_source_key", "ck_source_identity", "ck_source_status"},
    "source_entries": {"uq_source_entry_url", "ck_entry_url", "ck_entry_kind", "ck_entry_status",
                       "ck_entry_evidence", "ck_entry_enabled", "ck_entry_bool"},
    "articles": {"uq_article_dedup_url", "ck_article_identity", "ck_article_categories"},
    "bookmarks": set(),
    "update_jobs": {"ck_job_active_key", "ck_job_trigger", "ck_job_state",
                    "ck_job_date", "ck_job_finished"},
    "entry_results": {"uq_job_entry_result", "ck_result_state",
                      "ck_result_counts", "ck_result_finished"},
    "sessions": {"uq_session_digest"},
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


def _normalize_sql(value: str | None) -> str:
    """规范SQLite建表/索引SQL空白与标识符引号，用于当前迁移签名比较。"""
    return re.sub(r"\s+", " ", (value or "").replace('"', "").strip()).lower()


def _schema_signature(connection) -> dict[tuple[str, str, str], str]:
    """读取全部业务table/index/view/trigger定义；额外对象和约束表达式都会改变签名。"""
    return {
        (kind, name, table): _normalize_sql(sql)
        for kind, name, table, sql in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' AND name != 'alembic_version' "
            "AND type IN ('table','index','view','trigger')"
        )
    }


@lru_cache(maxsize=1)
def _expected_schema_signature() -> dict[tuple[str, str, str], str]:
    """由当前SQLAlchemy模型生成内存SQLite签名，避免只按对象名称信任伪造备份。"""
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        raw = engine.raw_connection()
        try:
            return _schema_signature(raw)
        finally:
            raw.close()
    finally:
        engine.dispose()


def _validate_database(path: Path) -> None:
    """确认快照完整且严格匹配当前迁移结构、索引、外键与引用数据。"""
    if not path.is_file():
        raise ApiError("backup_failed", "备份数据库不存在", 503)
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            checks = [row[0] for row in connection.execute("PRAGMA integrity_check")]
            if checks != ["ok"]:
                raise ApiError("backup_failed", "备份完整性检查失败", 503)
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
            if tables != set(_EXPECTED_COLUMNS) | {"alembic_version"}:
                raise ApiError("backup_failed", "数据库迁移结构不完整", 503)
            extra_objects = connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('view','trigger') LIMIT 1"
            ).fetchone()
            if extra_objects is not None:
                raise ApiError("backup_failed", "数据库包含未登记对象", 503)
            version_columns = tuple(
                (row[1], row[2].upper(), row[3], row[4], row[5])
                for row in connection.execute('PRAGMA table_info("alembic_version")')
            )
            if version_columns != (("version_num", "VARCHAR(32)", 1, None, 1),):
                raise ApiError("backup_failed", "数据库迁移表结构无效", 503)
            version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            if version != (_EXPECTED_REVISION,):
                raise ApiError("backup_failed", "数据库迁移版本不受支持", 503)
            if _schema_signature(connection) != _expected_schema_signature():
                raise ApiError("backup_failed", "数据库完整结构签名不匹配", 503)
            for table, expected_columns in _EXPECTED_COLUMNS.items():
                columns = tuple(
                    (row[1], row[2].upper(), row[3], row[4], row[5])
                    for row in connection.execute(f'PRAGMA table_info("{table}")')
                )
                if columns != expected_columns:
                    raise ApiError("backup_failed", "数据库列结构不匹配", 503)
                foreign_keys = {(row[3], row[2], row[4])
                                for row in connection.execute(f'PRAGMA foreign_key_list("{table}")')}
                if foreign_keys != _EXPECTED_FOREIGN_KEYS[table]:
                    raise ApiError("backup_failed", "数据库外键结构不匹配", 503)
                table_sql_row = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,),
                ).fetchone()
                table_sql = _normalize_sql(table_sql_row[0] if table_sql_row else None)
                if any(name not in table_sql for name in _EXPECTED_CONSTRAINT_NAMES[table]):
                    raise ApiError("backup_failed", "数据库约束结构不完整", 503)
                unique_columns = set()
                for _, index_name, unique, origin, _ in connection.execute(
                    f'PRAGMA index_list("{table}")'
                ):
                    if unique and origin == "u":
                        unique_columns.add(tuple(
                            row[2] for row in connection.execute(f'PRAGMA index_info("{index_name}")')
                        ))
                if unique_columns != _EXPECTED_UNIQUE_COLUMNS[table]:
                    raise ApiError("backup_failed", "数据库唯一约束不匹配", 503)
            index_sql = {
                name: _normalize_sql(sql) for name, sql in connection.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
                )
            }
            if index_sql != _EXPECTED_INDEX_SQL:
                raise ApiError("backup_failed", "数据库索引定义不匹配", 503)
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ApiError("backup_failed", "数据库存在孤立外键", 503)
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
        except OSError:
            # 已有健康备份不能因轮换权限失败终止worker；保留全部文件并允许下次tick重试。
            raise ApiError("backup_failed", "备份轮换失败", 503) from None
    return backup_once(db_path, folder, now)


_RESTORE_CONFIRMATION = "已确认损失备份后的写入"


def _assert_database_offline(path: Path) -> None:
    """除文件lease外再取得SQLite EXCLUSIVE，拒绝未遵守lease的活动连接。"""
    try:
        with closing(sqlite3.connect(str(path), timeout=0, isolation_level=None)) as connection:
            checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint is not None and checkpoint[0] != 0:
                raise sqlite3.OperationalError("WAL checkpoint busy")
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
