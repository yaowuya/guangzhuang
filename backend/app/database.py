"""SQLite 连接与短会话；提交由业务边界负责，失败和请求结束均释放资源。"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session


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
