"""以实际临时 SQLite 和迁移检验约束，不用模型 mock 代替持久化。"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_source_entry_constraints(db, entry_factory):
    """新入口默认待核验且禁用，同站相同地址不得重复建立。"""
    entry = entry_factory()
    assert (entry.verification_status, entry.enabled) == ("pending", False)
    assert db.scalar(text("PRAGMA foreign_keys")) == 1
    with pytest.raises(IntegrityError):
        entry_factory(source_id=entry.source_id, url=entry.url)
    db.rollback()


@pytest.mark.parametrize("invalid", [
    {"source_id": 999999},
    {"enabled": True},
    {"verification_status": "allowed"},
    {"verification_status": "restricted"},
    {"verification_status": "allowed", "verification_reason": " ", "verification_reference": "unit-ref"},
    {"verification_status": "restricted", "verification_reason": "明确受限", "verification_reference": "unit-ref", "enabled": True},
    {"verification_status": "partial"},
    {"kind": "article-body"},
])
def test_invalid_entry_permissions_are_rejected_by_database(db, entry_factory, invalid):
    """即使绕过服务层插入，孤儿关系、非法类型和无依据启用仍失败。"""
    with pytest.raises(IntegrityError):
        entry_factory(**invalid)
    db.rollback()


def test_different_entries_keep_independent_permissions(db, entry_factory):
    """一个入口核验通过，不影响同站另一个入口的待核验状态。"""
    first = entry_factory(verification_status="allowed", verification_reason="UNIT_ONLY",
                          verification_reference="unit-reference", enabled=True)
    second = entry_factory(source_id=first.source_id)
    assert first.enabled is True
    assert second.enabled is False
    assert second.verification_status == "pending"
    assert second.verification_reference is None


def test_source_migration_reversible_and_connections_enforce_foreign_keys(tmp_path):
    """在独立空库实际升级、回滚和再次升级，同时验证新连接的约束。"""
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from app.database import make_engine

    engine = make_engine(f"sqlite:///{(tmp_path / 'migration.sqlite3').as_posix()}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0001_sources")
            assert {"sources", "source_entries"} <= set(inspect(connection).get_table_names())
            command.downgrade(config, "base")
            assert "source_entries" not in inspect(connection).get_table_names()
            command.upgrade(config, "0001_sources")
        engine.dispose()
        with engine.connect() as reopened:
            assert reopened.scalar(text("PRAGMA foreign_keys")) == 1
            assert reopened.scalar(text("PRAGMA busy_timeout")) == 5000
    finally:
        engine.dispose()
