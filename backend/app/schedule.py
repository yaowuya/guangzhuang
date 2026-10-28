"""北京时间正常日程与当天有界补跑决策；次数由持久任务行证明。"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from .jobs import EnqueueResult, enqueue
from .models import UpdateJob
from .sources import eligible_entries

try:
    _SHANGHAI = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    # Windows开发运行时未携IANA数据；中国现行时区为无DST的UTC+8，Linux镜像仍使用ZoneInfo。
    _SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _local(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("日程时间必须包含时区")
    return now.astimezone(_SHANGHAI)


def schedule_due(db: Session, now: datetime) -> EnqueueResult | None:
    """常驻 tick 只在北京时间07:30分钟窗口创建正常日程，迟到由catchup负责。"""
    local = _local(now)
    if (local.hour, local.minute) != (7, 30):
        return None
    existing = db.scalar(select(UpdateJob.id).where(
        UpdateJob.schedule_date == local.date(),
        UpdateJob.trigger.in_(("schedule", "catchup")),
    ).limit(1))
    if existing is not None:
        return None
    active = db.scalar(select(UpdateJob.id).where(
        UpdateJob.state.in_(("pending", "running")),
    ).limit(1))
    if active is not None:
        return None
    ids = [entry.id for entry in eligible_entries(db)]
    if not ids:
        return None
    result = enqueue(db, "schedule", ids, local.date(), now)
    return None if result.reused else result


def tick(db: Session, now: datetime) -> EnqueueResult | None:
    """空闲 worker 的一次日程维护；catchup 在下一任务接入。"""
    return schedule_due(db, now)
