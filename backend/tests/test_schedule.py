"""北京时间日程、当天补跑与恢复顺序测试。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.jobs import enqueue
from app.schedule import catchup_due, schedule_due, tick
from app.sources import apply_verification, eligible_entries, load_registry, seed_sources


def approve_schedule_entry(db, settings, now, keys=("prtimes-rss",)):
    settings.source_config.write_text(Path("config/sources.json").read_text(encoding="utf-8"), encoding="utf-8")
    db.info["source_config"] = settings.source_config
    specs = load_registry(settings.source_config)
    seed_sources(db, specs)
    for key in keys:
        spec = next(item for item in specs if item.key == key)
        apply_verification(db, {
            "entry_key": spec.key, "verification_status": "allowed",
            "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
            "automation_allowed": True, "title_storage_allowed": True,
        }, {
            "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
            "title_count": 1, "final_url": spec.url, "error": None,
        }, now)
    return [entry for entry in eligible_entries(db) if entry.entry_key in keys]


def test_beijing_0730_schedule(db, settings):
    """UTC 23:30 对应次日北京时间07:30，且同日只创建一次正常日程。"""
    before = datetime(2026, 10, 26, 23, 29, 59, tzinfo=UTC)
    due = datetime(2026, 10, 26, 23, 30, tzinfo=UTC)
    approve_schedule_entry(db, settings, due)
    assert schedule_due(db, before) is None
    result = schedule_due(db, due)
    assert result.job.trigger == "schedule"
    assert str(result.job.schedule_date) == "2026-10-27"
    assert schedule_due(db, datetime(2026, 10, 26, 23, 30, 1, tzinfo=UTC)) is None


def test_schedule_does_not_replay_or_parallel_manual_work(db, settings, job_factory):
    """07:30外不回放；活动手动任务优先，naive时间被拒绝。"""
    due = datetime(2026, 10, 26, 23, 30, tzinfo=UTC)
    approve_schedule_entry(db, settings, due)
    active = job_factory(state="pending")
    assert schedule_due(db, due) is None
    active.state = "succeeded"
    active.finished_at = due
    active.entries[0].state = "succeeded"
    active.entries[0].finished_at = due
    db.commit()
    assert schedule_due(db, due - timedelta(seconds=1)) is None
    assert schedule_due(db, due + timedelta(minutes=1)) is None
    with pytest.raises(ValueError):
        schedule_due(db, datetime(2026, 10, 27, 7, 30))


def test_existing_catchup_blocks_normal_schedule_and_tick_uses_same_rule(db, settings):
    """同日已有catchup即为运行次数证据，不再补一条schedule。"""
    due = datetime(2026, 10, 26, 23, 30, tzinfo=UTC)
    approve_schedule_entry(db, settings, due)
    from app.sources import eligible_entries

    entry_id = eligible_entries(db)[0].id
    catchup = enqueue(db, "catchup", [entry_id], due.astimezone(timezone(timedelta(hours=8))).date(), due)
    catchup.job.state = "failed"
    catchup.job.finished_at = due
    catchup.job.entries[0].state = "failed"
    catchup.job.entries[0].finished_at = due
    db.commit()
    assert schedule_due(db, due) is None
    assert tick(db, due) is None


def test_missing_partial_and_restarts(db, settings, now):
    """当天无日程在07:30后全量补跑一次，终态后重启不再新建catchup。"""
    entries = approve_schedule_entry(db, settings, now)
    after = datetime(2026, 10, 27, 2, 0, tzinfo=UTC)
    result = catchup_due(db, after)
    assert result.job.trigger == "catchup"
    assert [row.entry_id for row in result.job.entries] == [entries[0].id]
    result.job.state = "interrupted"
    result.job.finished_at = after
    result.job.entries[0].state = "interrupted"
    result.job.entries[0].finished_at = after
    db.commit()
    assert catchup_due(db, after) is None


def test_partial_schedule_only_retries_unsuccessful_current_entries(db, settings, job_factory, now):
    """有日程结果时只补非成功与当前eligible交集，新禁用和成功入口排除。"""
    entries = approve_schedule_entry(
        db, settings, now, ("prtimes-rss", "happi-rss", "qingyan-list"))
    local_date = datetime(2026, 10, 27, 2, 0, tzinfo=UTC).astimezone(
        timezone(timedelta(hours=8))).date()
    scheduled = job_factory(
        trigger="schedule", schedule_date=local_date, state="partial",
        entry_ids=[entry.id for entry in entries],
        result_states=["succeeded", "failed", "interrupted"],
    )
    entries[2].enabled = False
    db.commit()
    result = catchup_due(db, datetime(2026, 10, 27, 2, 0, tzinfo=UTC))
    assert [row.entry_id for row in result.job.entries] == [entries[1].id]
    assert scheduled.entries[0].state == "succeeded"


def test_catchup_before_time_success_and_no_candidate_do_not_consume(db, settings, job_factory, now):
    """07:30前不补；成功日程不补；无候选不写次数行，之后启用仍可补。"""
    entries = approve_schedule_entry(db, settings, now)
    before = datetime(2026, 10, 26, 23, 29, 59, tzinfo=UTC)
    assert catchup_due(db, before) is None
    local_date = datetime(2026, 10, 27, 2, 0, tzinfo=UTC).astimezone(
        timezone(timedelta(hours=8))).date()
    succeeded = job_factory(
        trigger="schedule", schedule_date=local_date, state="succeeded",
        entry_ids=[entries[0].id], result_states=["succeeded"],
    )
    assert catchup_due(db, datetime(2026, 10, 27, 2, 0, tzinfo=UTC)) is None
    # 改用次日：入口先禁用，不产生catchup；恢复后仍可创建。
    entries[0].enabled = False
    db.commit()
    next_day = datetime(2026, 10, 28, 2, 0, tzinfo=UTC)
    assert catchup_due(db, next_day) is None
    entries[0].enabled = True
    db.commit()
    assert catchup_due(db, next_day).job.trigger == "catchup"
    assert succeeded.state == "succeeded"


def test_manual_activity_delays_catchup_until_it_finishes(db, settings, job_factory, now):
    """活动手动任务不并行；终态提交后同日tick再创建一次catchup。"""
    approve_schedule_entry(db, settings, now)
    active = job_factory(state="pending")
    after = datetime(2026, 10, 27, 2, 0, tzinfo=UTC)
    assert catchup_due(db, after) is None
    active.state = "succeeded"
    active.finished_at = after
    active.entries[0].state = "succeeded"
    active.entries[0].finished_at = after
    db.commit()
    assert catchup_due(db, after).job.trigger == "catchup"


def test_concurrent_catchup_ticks_create_one_daily_row(db, settings, now):
    """并发迟到tick由活动/日期唯一约束收敛为一条catchup。"""
    approve_schedule_entry(db, settings, now)
    after = datetime(2026, 10, 27, 2, 0, tzinfo=UTC)

    def run():
        with Session(db.bind, expire_on_commit=False) as other:
            other.info.update(db.info)
            result = catchup_due(other, after)
            return None if result is None else result.job.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: run(), range(2)))
    assert len([value for value in ids if value is not None]) == 1


def test_concurrent_schedule_ticks_create_one_daily_row(db, settings):
    """两个worker式连接竞争同一07:30窗口，日期/活动索引只允许一个新任务。"""
    due = datetime(2026, 10, 26, 23, 30, tzinfo=UTC)
    approve_schedule_entry(db, settings, due)

    def run():
        with Session(db.bind, expire_on_commit=False) as other:
            other.info.update(db.info)
            result = schedule_due(other, due)
            return None if result is None else result.job.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: run(), range(2)))
    created = [value for value in ids if value is not None]
    assert len(created) == 1
