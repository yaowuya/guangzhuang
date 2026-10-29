"""独立串行 worker：短事务认领、逐入口提交与跨进程文件锁。"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
import logging
from pathlib import Path
import time

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.infrastructure.persistence.database import _file_lock, application_lease, db_session, make_engine
from app.core.exceptions import ApiError
from app.application.ingestion import ingest_entry, safe_error
from app.infrastructure.persistence.models import EntryResult, SourceEntry, UpdateJob
from app.infrastructure.http.safe_client import SafeClient
from app.application.scheduling import tick
from app.application.sources import eligible_entries


@contextmanager
def single_worker_lock(path: str | Path) -> Iterator[object]:
    """非阻塞独占 worker 锁；生产 Linux 使用 flock 拒绝第二实例。"""
    with _file_lock(path, exclusive=True, nonblocking=True) as handle:
        yield handle


def claim_next(db: Session, now: datetime) -> UpdateJob | None:
    """条件更新保证一个 pending 只认领一次，立即提交以释放 SQLite 写锁。"""
    candidate = select(UpdateJob.id).where(
        UpdateJob.state == "pending",
    ).order_by(UpdateJob.id).limit(1).scalar_subquery()
    try:
        job_id = db.execute(
            update(UpdateJob).where(
                UpdateJob.id == candidate,
                UpdateJob.state == "pending",
            ).values(state="running", started_at=now).returning(UpdateJob.id)
        ).scalar_one_or_none()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return db.get(UpdateJob, job_id) if job_id is not None else None


def finish_job(db: Session, job: UpdateJob, now: datetime) -> UpdateJob:
    """仅在全部入口已有终态时聚合 succeeded/partial/failed 并释放活动索引。"""
    db.refresh(job)
    db.expire(job, ["entries"])
    states = [result.state for result in job.entries]
    if not states or any(state in {"pending", "running"} for state in states):
        raise ValueError("任务仍有未完成入口")
    succeeded = states.count("succeeded")
    if succeeded == len(states):
        job.state = "succeeded"
    elif succeeded == 0:
        job.state = "failed"
    else:
        job.state = "partial"
    job.finished_at = now
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return job


def process_job(
    db: Session,
    job: UpdateJob,
    client_factory: Callable[[SourceEntry], object],
    now_fn: Callable[[], datetime],
) -> UpdateJob:
    """串行处理入口；running短提交后才联网，成功条目与结果由ingest_entry同事务提交。"""
    if job.state != "running":
        raise ValueError("只能处理已认领任务")
    for result in list(job.entries):
        if result.state != "pending":
            continue
        result.state = "running"
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        try:
            allowed = {entry.id: entry for entry in eligible_entries(db)}
            entry = allowed.get(result.entry_id)
            if entry is None:
                raise ApiError("source_not_enabled", "入口未经核验或未启用", 409)
            client = client_factory(entry)
            ingest_entry(db, entry, client, now_fn(), result_id=result.id)
        except Exception as error:
            db.rollback()
            message = safe_error(error)
            failed = db.get(EntryResult, result.id)
            source_entry = db.get(SourceEntry, result.entry_id)
            if failed is None:
                raise RuntimeError("入口任务结果关系已损坏") from None
            failed.state = "failed"
            failed.error = message
            failed.finished_at = now_fn()
            if source_entry is not None:
                source_entry.last_error = message
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise
            logging.getLogger("beauty_intelligence.worker").warning(
                "entry_failed",
                extra={"job_id": job.id, "entry_id": result.entry_id,
                       "error_type": type(error).__name__},
            )
    return finish_job(db, job, now_fn())


def settle_interrupted(db: Session, now: datetime) -> int:
    """仅在持有worker单例锁的启动阶段结算旧running；正常pending队列保持可认领。"""
    jobs = list(db.scalars(select(UpdateJob).where(UpdateJob.state == "running").order_by(UpdateJob.id)))
    for job in jobs:
        db.expire(job, ["entries"])
        for result in job.entries:
            if result.state in {"pending", "running"}:
                result.state = "interrupted"
                result.finished_at = now
                result.error = "上次更新进程中断"
        job.state = "interrupted"
        job.finished_at = now
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    logger = logging.getLogger("beauty_intelligence.worker")
    for job in jobs:
        logger.warning("job_interrupted", extra={"job_id": job.id})
    return len(jobs)


# fp-debt: 当前个人单机与固定来源范围采用一个串行 worker + SQLite，避免引入无证据的队列服务。
# 上限：单台主机、一个 API、一个 worker；触发：实测更新无法在日程窗口完成、锁冲突影响阅读，或需要多机写入。
# 升级：将持久任务/幂等语义迁移至 PostgreSQL 与受控队列；风险 owner 见 fp-docs/changes/beauty-intelligence-mvp/design/backend.md#风险迁移发布回滚与监控。
def worker_loop(settings: Settings | None = None) -> None:
    """独立进程持续认领持久任务；不在 API 进程创建线程或读取浏览器状态。"""
    resolved = settings or Settings.from_environment()
    engine = make_engine(resolved.database_url)
    try:
        with single_worker_lock(resolved.data_dir / "worker.lock"):
            with application_lease(resolved.data_dir / "application.lock", exclusive=False):
                with db_session(engine) as db:
                    db.info.update(
                        source_config=resolved.source_config,
                        rules_config=resolved.rules_config,
                        backup_dir=resolved.backup_dir,
                    )
                    settle_interrupted(db, datetime.now(UTC))
                    while True:
                        job = claim_next(db, datetime.now(UTC))
                        if job is None:
                            scheduled = tick(db, datetime.now(UTC))
                            if scheduled is None:
                                time.sleep(1)
                            continue
                        process_job(db, job, SafeClient.from_spec, lambda: datetime.now(UTC))
    finally:
        engine.dispose()


if __name__ == "__main__":
    worker_loop()
