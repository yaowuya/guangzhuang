"""持久更新任务的短事务入队、复用与重试候选选择。"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .errors import ApiError
from .models import EntryResult, Source, SourceEntry, UpdateJob
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


def retry_job(db: Session, job_id: int, now: datetime) -> EnqueueResult:
    """保留原结果，只对失败或中断且当前仍可用的入口新建重试任务。"""
    old = db.get(UpdateJob, job_id)
    if old is None:
        raise ApiError("job_not_found", "任务不存在", 404)
    active = _active(db)
    if active is not None:
        return EnqueueResult(job=active, reused=True)
    allowed = {entry.id for entry in eligible_entries(db)}
    ids = [result.entry_id for result in old.entries
           if result.state in {"failed", "interrupted"} and result.entry_id in allowed]
    if not ids:
        raise ApiError("no_retryable_entries", "没有当前可重试的入口", 409)
    return enqueue(db, "retry", ids, None, now)


class EntryResultOut(BaseModel):
    entry_id: int
    source_id: int
    source_name: str
    entry_url: str
    state: Literal["pending", "running", "succeeded", "failed", "interrupted"]
    count_added: int
    count_updated: int
    error: str | None
    finished_at: datetime | None


class JobOut(BaseModel):
    id: int
    trigger: Literal["schedule", "catchup", "refresh", "retry"]
    state: Literal["pending", "running", "succeeded", "partial", "failed", "interrupted"]
    schedule_date: date | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    count_added: int
    count_updated: int
    entries: list[EntryResultOut]


def job_out(db: Session, job: UpdateJob) -> JobOut:
    """由入口结果聚合计数并补充来源身份，不混用许可或网站汇总状态。"""
    rows = []
    for result in job.entries:
        entry = db.get(SourceEntry, result.entry_id)
        source = db.get(Source, entry.source_id) if entry is not None else None
        if entry is None or source is None:
            raise RuntimeError("任务入口关系已损坏")
        rows.append(EntryResultOut(
            entry_id=entry.id, source_id=source.id, source_name=source.name,
            entry_url=entry.url, state=result.state,
            count_added=result.count_added, count_updated=result.count_updated,
            error=result.error, finished_at=result.finished_at,
        ))
    return JobOut(
        id=job.id, trigger=job.trigger, state=job.state,
        schedule_date=job.schedule_date, created_at=job.created_at,
        started_at=job.started_at, finished_at=job.finished_at,
        count_added=sum(row.count_added for row in rows),
        count_updated=sum(row.count_updated for row in rows),
        entries=rows,
    )


def current_job(db: Session) -> JobOut | None:
    """活动任务优先；没有活动时返回最近任务，从未创建时明确为 null。"""
    job = _active(db)
    if job is None:
        job = db.scalar(select(UpdateJob).order_by(UpdateJob.created_at.desc(), UpdateJob.id.desc()))
    return job_out(db, job) if job is not None else None
