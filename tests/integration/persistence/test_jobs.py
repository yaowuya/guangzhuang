"""持久更新任务入队、并发复用与重试候选测试。"""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.application.jobs import enqueue, enqueue_refresh, retry_job
from app.infrastructure.persistence.models import EntryResult, UpdateJob
from app.application.sources import apply_verification, eligible_entries, seed_sources
from app.infrastructure.configuration import load_registry


def approve_entries(db, settings, now, keys=("prtimes-rss",)):
    """用合成证据批准固定入口；不执行网络或创建真实许可文件。"""
    registry = json.loads(Path("config/sources.json").read_text(encoding="utf-8"))
    for item in registry:
        if item["key"] in keys and item["kind"] == "public_list":
            item["selection"] = {
                "container": "main", "item": "article", "title": "h2", "link": "a",
            }
    settings.source_config.write_text(json.dumps(registry), encoding="utf-8")
    db.info["source_config"] = settings.source_config
    specs = load_registry(settings.source_config)
    seed_sources(db, specs)
    for key in keys:
        spec = next(item for item in specs if item.key == key)
        apply_verification(db, {
            "entry_key": key, "verification_status": "allowed",
            "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
            "automation_allowed": True, "title_storage_allowed": True,
            "selection": spec.selection,
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


def test_retry_only_unsuccessful_eligible_entries(db, settings, job_factory, now):
    """重试取失败/中断与当前许可的交集，不碰原成功结果或后来禁用入口。"""
    entries = approve_entries(db, settings, now, ("prtimes-rss", "happi-rss", "qingyan-list"))
    old = job_factory(
        state="partial", entry_ids=[entry.id for entry in entries],
        result_states=["succeeded", "failed", "interrupted"],
    )
    old.entries[0].count_added = 3
    entries[2].enabled = False
    db.commit()
    result = retry_job(db, old.id, now)
    assert result.job.trigger == "retry"
    assert {row.entry_id for row in result.job.entries} == {entries[1].id}
    db.refresh(old.entries[0])
    assert (old.entries[0].state, old.entries[0].count_added) == ("succeeded", 3)


def test_retry_404_active_reuse_and_empty_candidates(db, settings, job_factory, now):
    """不存在优先404；存在活动任务直接复用；无当前可重试入口409。"""
    entries = approve_entries(db, settings, now)
    active = job_factory(state="pending", entry_ids=[entries[0].id])
    with pytest.raises(ApiError) as missing:
        retry_job(db, 999999, now)
    assert (missing.value.status, missing.value.code) == (404, "job_not_found")
    reused = retry_job(db, active.id, now)
    assert reused.reused is True and reused.job.id == active.id
    active.state = "succeeded"
    active.finished_at = now
    active.entries[0].state = "succeeded"
    active.entries[0].finished_at = now
    db.commit()
    with pytest.raises(ApiError) as empty:
        retry_job(db, active.id, now)
    assert (empty.value.status, empty.value.code) == (409, "no_retryable_entries")


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
