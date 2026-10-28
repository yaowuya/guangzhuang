"""迁移只需要数据库配置；独立于网页登录密钥和外站来源。"""

import os

from alembic import context

from app.database import make_engine
from app.models import Base

config = context.config


def apply_migrations(connection):
    """复用显式测试连接或部署连接，按 Alembic 顺序执行版本。"""
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def configured_url():
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise ValueError("迁移需要显式 DATABASE_URL")
    return url


if context.is_offline_mode():
    context.configure(url=configured_url(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    provided = config.attributes.get("connection")
    if provided is not None:
        apply_migrations(provided)
    else:
        engine = make_engine(configured_url())
        try:
            with engine.connect() as connection:
                apply_migrations(connection)
        finally:
            engine.dispose()
