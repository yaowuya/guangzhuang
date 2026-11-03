"""FastAPI 请求依赖；把 Web 生命周期适配到持久化会话。"""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.infrastructure.persistence.database import db_session, make_engine


def get_db(request: Request) -> Iterator[Session]:
    """按请求创建短 SQLite 会话并注入固定来源与分类配置。"""
    settings = request.app.state.settings
    engine = make_engine(settings.database_url)
    try:
        with db_session(engine) as session:
            session.info.update(
                rules_config=settings.rules_config,
                source_config=settings.source_config,
            )
            yield session
    finally:
        engine.dispose()
