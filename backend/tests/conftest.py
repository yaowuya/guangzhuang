"""仅提供隔离测试环境，不导入真实来源、部署密码或生产数据。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient


@pytest.fixture
def now() -> datetime:
    """提供可复现的 UTC 时间；不依赖测试机本地时区。"""
    return datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path: Path):
    """生成仅供本次测试使用的配置；凭据不落仓库或日志。"""
    from app.config import Settings

    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
        public_origin="https://unit.example",
        password_hash=PasswordHasher().hash("unit-password"),
        csrf_key="unit-only-csrf-key-not-a-production-secret",
        source_config=tmp_path / "sources.json",
        rules_config=tmp_path / "classification.json",
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        trusted_gateway_ip="",
    )


@pytest.fixture
def client(settings):
    """在 HTTPS 测试入口观察公开响应，不伪造业务来源。"""
    from app.main import create_app

    return TestClient(
        create_app(settings),
        base_url=settings.public_origin,
        raise_server_exceptions=False,
    )


@pytest.fixture
def db(settings):
    """通过真正的 Alembic 升级建立每测独立库，结束后释放所有连接。"""
    from alembic import command
    from alembic.config import Config
    from app.database import db_session, make_engine

    engine = make_engine(settings.database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with db_session(engine) as session:
            session.info.update(rules_config=settings.rules_config, source_config=settings.source_config)
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def entry_factory(db):
    """合成来源仅存在测试库；默认待核验禁用，绝非生产授权证据。"""
    from uuid import uuid4
    from sqlalchemy import select
    from app.models import Source, SourceEntry

    def create(**overrides):
        if "source_id" not in overrides:
            source = db.scalar(select(Source).where(Source.key == "unit"))
            if source is None:
                source = Source(key="unit", name="UNIT_ONLY 来源")
                db.add(source)
                db.flush()
            overrides["source_id"] = source.id
        values = {"url": f"https://unit.example/{uuid4().hex}", "kind": "rss", **overrides}
        entry = SourceEntry(**values)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    return create


@pytest.fixture
def job_factory(db, entry_factory, now):
    """在隔离库创建持久任务及显式结果，只用于任务/恢复单元边界。"""
    from app.models import EntryResult, UpdateJob

    def create(**overrides):
        entry_ids = overrides.pop("entry_ids", None)
        result_states = overrides.pop("result_states", None)
        if entry_ids is None:
            entry_ids = [entry_factory().id for _ in (result_states or ["pending"])]
        if result_states is None:
            result_states = ["pending"] * len(entry_ids)
        if len(result_states) != len(entry_ids):
            raise ValueError("测试入口与结果数量不一致")
        trigger = overrides.get("trigger", "refresh")
        state = overrides.get("state", "pending")
        values = {"trigger": trigger, "state": state, "created_at": now, "active_key": 1,
                  "schedule_date": now.date() if trigger in {"schedule", "catchup"} else None,
                  "started_at": now if state != "pending" else None,
                  "finished_at": now if state not in {"pending", "running"} else None,
                  **overrides}
        job = UpdateJob(**values)
        job.entries = [EntryResult(entry_id=entry_id, state=result_state,
                                  finished_at=now if result_state not in {"pending", "running"} else None)
                       for entry_id, result_state in zip(entry_ids, result_states, strict=True)]
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    return create


@pytest.fixture
def article_factory(db, entry_factory, now):
    """创建临时标题记录供存储边界测试；不获取或伪造真实来源。"""
    from uuid import uuid4
    from app.models import Article

    def create(**overrides):
        if "first_entry_id" not in overrides:
            entry = entry_factory()
            overrides.setdefault("source_id", entry.source_id)
            overrides["first_entry_id"] = entry.id
        url = f"https://unit.example/article/{uuid4().hex}"
        values = {
            "original_url": url, "dedup_url": url, "title": "UNIT_ONLY 标题",
            "search_text": "unit_only 标题", "category_codes": [], "updated_at": now,
            **overrides,
        }
        article = Article(**values)
        db.add(article)
        db.commit()
        db.refresh(article)
        return article

    return create
