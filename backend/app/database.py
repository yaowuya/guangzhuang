"""SQLite 连接与短会话；提交由业务边界负责，失败和请求结束均释放资源。"""

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session


@contextmanager
def _file_lock(path: str | Path, *, exclusive: bool, nonblocking: bool) -> Iterator[object]:
    """跨进程锁底层：Linux flock 提供共享/独占，Windows仅用于本地互斥开发。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = target.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            mode = msvcrt.LK_NBLCK if nonblocking else msvcrt.LK_LOCK
            try:
                msvcrt.locking(handle.fileno(), mode, 1)
            except OSError:
                raise RuntimeError("应用锁已被其它进程持有") from None
            try:
                yield handle
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            if nonblocking:
                operation |= fcntl.LOCK_NB
            try:
                fcntl.flock(handle.fileno(), operation)
            except OSError:
                raise RuntimeError("应用锁已被其它进程持有") from None
            try:
                yield handle
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


@contextmanager
def application_lease(path: str | Path, exclusive: bool = False) -> Iterator[object]:
    """API/worker持共享租约，离线恢复持非阻塞独占租约。"""
    with _file_lock(path, exclusive=exclusive, nonblocking=exclusive) as handle:
        yield handle


def make_engine(url: str) -> Engine:
    """为每个实际连接开启外键和有界等待，不在创建引擎时建库或迁移。"""
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 5})

    @event.listens_for(engine, "connect")
    def configure_connection(connection, record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

    return engine


@contextmanager
def db_session(engine: Engine) -> Iterator[Session]:
    """借出一次会话；不隐式提交，异常或离开时回滚未提交事务并关闭。"""
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            session.rollback()


def get_db(request: Request) -> Iterator[Session]:
    """按请求提供真实 SQLite 会话及固定来源配置，不读取外站或自动迁移。"""
    settings = request.app.state.settings
    # 当前无常驻连接生命周期；请求内引擎用完立即销毁，避免测试或启动时泄漏。
    engine = make_engine(settings.database_url)
    try:
        with db_session(engine) as session:
            session.info.update(rules_config=settings.rules_config, source_config=settings.source_config)
            yield session
    finally:
        engine.dispose()
