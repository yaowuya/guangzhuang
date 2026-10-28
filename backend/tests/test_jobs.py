"""持久更新任务入队、并发复用与重试候选测试。"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.jobs import enqueue, enqueue_refresh
from app.models import EntryResult, UpdateJob
from app.sources import apply_verification, eligible_entries, load_registry, seed_sources


def approve_entries(db, settings, now, keys=("prtimes-rss",)):
    """用合成证据批准固定入口；不执行网络或创建真实许可文件。"""
    settings.source_config.write_text(Path("config/sources.json").read_text(encoding="utf-8"), encoding="utf-8")
    db.info["source_config"] = settings.source_config
    specs = load_registry(settings.source_config)
    seed_sources(db, specs)
    for key in keys:
        spec = next(item for item in specs if item.key == key)
        apply_verification(db, {
            "entry_key": key, "verification_status": "allowed",
            "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
            "automation_allowed": True, "title_storage_allowed": True,
        }, {
            "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
            "title_count": 1, "final_url": spec.url, "error": None,
        }, now)
    return eligible_entries(db)


def test_concurrent_refresh_reuses_active(db, settings, now):
    """独立会话并发刷新最终只产生一个活动任务及一组入口结果。"""
    approve_entries(db, settings, now)

    def run():
        with Session(db.bind, expire_on_commit=False) as other:
            other.info.update(db.info)
            result = enqueue_refresh(other, now)
            return result.job.id, result.reused

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert len({result[0] for result in results}) == 1
    assert sorted(result[1] for result in results) == [False, True]


def test_refresh_candidates_atomic_results_and_terminal_allows_new(db, settings, now):
    """所有当前合格入口各有一条结果；活动复用，终态后才能建立下一任务。"""
    entries = approve_entries(db, settings, now, ("prtimes-rss", "happi-rss"))
    first = enqueue_refresh(db, now)
    assert first.reused is False
    assert first.job.state == "pending"
    assert {result.entry_id for result in first.job.entries} == {entry.id for entry in entries}
    first.job.state = "running"
    first.job.started_at = now
    db.commit()
    assert enqueue_refresh(db, now).job.id == first.job.id
    first.job.state = "succeeded"
    first.job.finished_at = now
    db.commit()
    second = enqueue_refresh(db, now)
    assert second.reused is False and second.job.id != first.job.id
    assert db.scalar(select(func.count()).select_from(EntryResult)) == 4


def test_no_enabled_sources_and_active_priority(db, settings, job_factory, now):
    """无入口409，但已有活动任务即使配置暂不可读仍优先复用。"""
    approve_entries(db, settings, now, ())
    with pytest.raises(ApiError) as empty:
        enqueue_refresh(db, now)
    assert (empty.value.status, empty.value.code) == (409, "no_enabled_sources")
    active = job_factory(state="pending")
    db.info.pop("source_config", None)
    reused = enqueue_refresh(db, now)
    assert reused.reused is True and reused.job.id == active.id


def test_enqueue_rolls_back_half_job_and_daily_identity_reuses_terminal(db, settings, now):
    """外键失败不遗留半个Job；同日日程终态仍复用当日记录。"""
    entries = approve_entries(db, settings, now)
    with pytest.raises(IntegrityError):
        enqueue(db, "refresh", [entries[0].id, 999999], None, now)
    assert db.scalar(select(func.count()).select_from(UpdateJob)) == 0
    assert db.scalar(select(func.count()).select_from(EntryResult)) == 0

    daily = enqueue(db, "schedule", [entries[0].id], now.date(), now)
    daily.job.state = "succeeded"
    daily.job.finished_at = now
    db.commit()
    repeated = enqueue(db, "schedule", [entries[0].id], now.date(), now)
    assert repeated.reused is True and repeated.job.id == daily.job.id
    assert db.scalar(select(func.count()).select_from(UpdateJob)) == 1
