"""北京时间正常日程与当天有界补跑决策；次数由持久任务行证明。"""

from datetime import datetime, time as clock_time, timedelta, timezone
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from .backup import daily_backup
from .errors import ApiError
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


def catchup_due(db: Session, now: datetime) -> EnqueueResult | None:
    """当天最多一条catchup；缺日程全选，有结果只补非成功且当前仍可用的入口。"""
    local = _local(now)
    if local.time().replace(tzinfo=None) < clock_time(7, 30):
        return None
    used = db.scalar(select(UpdateJob.id).where(
        UpdateJob.trigger == "catchup", UpdateJob.schedule_date == local.date(),
    ).limit(1))
    if used is not None:
        return None
    active = db.scalar(select(UpdateJob.id).where(
        UpdateJob.state.in_(("pending", "running")),
    ).limit(1))
    if active is not None:
        return None
    scheduled = db.scalar(select(UpdateJob).where(
        UpdateJob.trigger == "schedule", UpdateJob.schedule_date == local.date(),
    ).order_by(UpdateJob.id.desc()))
    if scheduled is not None and scheduled.state == "succeeded":
        return None
    allowed = {entry.id for entry in eligible_entries(db)}
    if scheduled is None or not scheduled.entries:
        ids = sorted(allowed)
    else:
        ids = sorted(
            result.entry_id for result in scheduled.entries
            if result.state != "succeeded" and result.entry_id in allowed
        )
    if not ids:
        return None
    result = enqueue(db, "catchup", ids, local.date(), now)
    return None if result.reused else result


def tick(db: Session, now: datetime) -> EnqueueResult | None:
    """空闲worker先调度/补跑；无任务时执行当日在线备份，失败留待下次tick重试。"""
    scheduled = schedule_due(db, now)
    if scheduled is not None:
        return scheduled
    recovered = catchup_due(db, now)
    if recovered is not None:
        return recovered
    backup_dir = db.info.get("backup_dir")
    if backup_dir is None:
        return None
    local_day = _local(now).date()
    if db.info.get("backup_validated_date") == local_day:
        return None
    # 释放日程查询事务后再用独立SQLite连接在线备份；成功日期仅驻本worker会话，重启最多复核一次。
    db.rollback()
    try:
        daily_backup(db.bind.url.database, backup_dir, now)
        db.info["backup_validated_date"] = local_day
    except ApiError:
        logging.getLogger("beauty_intelligence.backup").error("backup_failed")
    return None
