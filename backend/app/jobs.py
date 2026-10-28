"""持久更新任务的短事务入队、复用与重试候选选择。"""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .errors import ApiError
from .models import EntryResult, UpdateJob
from .sources import eligible_entries


@dataclass(frozen=True)
class EnqueueResult:
    """返回持久任务及是否复用；请求线程不执行来源网络。"""

    job: UpdateJob
    reused: bool


def _active(db: Session) -> UpdateJob | None:
    return db.scalar(select(UpdateJob).where(
        UpdateJob.state.in_(("pending", "running")),
    ).order_by(UpdateJob.id))


def enqueue(
    db: Session,
    trigger: str,
    entry_ids: list[int],
    schedule_date: date | None,
    now: datetime,
) -> EnqueueResult:
    """原子创建任务与唯一入口结果；数据库部分唯一索引解决并发竞争。"""
    if trigger not in {"refresh", "retry", "schedule", "catchup"}:
        raise ValueError("任务触发类型无效")
    if (trigger in {"schedule", "catchup"}) != (schedule_date is not None):
        raise ValueError("日程任务日期无效")
    ids = list(dict.fromkeys(entry_ids))
    if not ids or any(type(entry_id) is not int or entry_id <= 0 for entry_id in ids):
        raise ValueError("任务入口列表无效")
    job = UpdateJob(
        trigger=trigger, state="pending", created_at=now,
        schedule_date=schedule_date, active_key=1,
    )
    job.entries = [EntryResult(entry_id=entry_id, state="pending") for entry_id in ids]
    db.add(job)
    try:
        db.commit()
        return EnqueueResult(job=job, reused=False)
    except IntegrityError:
        db.rollback()
        active = _active(db)
        if active is not None:
            return EnqueueResult(job=active, reused=True)
        if trigger in {"schedule", "catchup"}:
            existing = db.scalar(select(UpdateJob).where(
                UpdateJob.trigger == trigger,
                UpdateJob.schedule_date == schedule_date,
            ).order_by(UpdateJob.id.desc()))
            if existing is not None:
                return EnqueueResult(job=existing, reused=True)
        raise
    except SQLAlchemyError:
        db.rollback()
        raise


def enqueue_refresh(db: Session, now: datetime) -> EnqueueResult:
    """只创建数据库任务；已有活动优先返回，不等待来源网络。"""
    active = _active(db)
    if active is not None:
        return EnqueueResult(job=active, reused=True)
    ids = [entry.id for entry in eligible_entries(db)]
    if not ids:
        raise ApiError("no_enabled_sources", "没有已核验且启用的入口", 409)
    return enqueue(db, "refresh", ids, None, now)
