"""独立串行 worker 的原子认领、逐入口提交和进程锁测试。"""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Article, Source
from app.worker import (
    application_lease, claim_next, process_job, settle_interrupted, single_worker_lock,
)


def test_serial_claim_and_partial_results(worker_lab, now):
    """两个连接只认领一次；一个成功一个失败形成partial并保留成功条目。"""
    job = worker_lab.pending_job(entries=2)
    worker_lab.succeed(0, title="A", url="https://example.org/a")
    worker_lab.fail(1, code="source_unavailable")
    claimed = claim_next(worker_lab.db, now)
    assert claimed.id == job.id
    assert claim_next(worker_lab.other_db, now) is None
    process_job(worker_lab.db, claimed, worker_lab.client_factory, worker_lab.now)
    worker_lab.db.refresh(job)
    assert job.state == "partial"
    assert [result.state for result in job.entries] == ["succeeded", "failed"]
    assert job.entries[0].count_added == 1
    assert worker_lab.db.scalar(select(func.count()).select_from(Article)) == 1


def test_all_failed_and_all_zero_success_are_distinct(worker_lab, now):
    """全失败为failed；合法零条的入口仍是succeeded而非读取失败。"""
    failed_job = worker_lab.pending_job(entries=1)
    worker_lab.fail(0)
    process_job(worker_lab.db, claim_next(worker_lab.db, now),
                worker_lab.client_factory, worker_lab.now)
    worker_lab.db.refresh(failed_job)
    assert failed_job.state == "failed" and failed_job.entries[0].state == "failed"

    zero_job = worker_lab.pending_job(entries=1)
    worker_lab.zero(0)
    process_job(worker_lab.db, claim_next(worker_lab.db, now),
                worker_lab.client_factory, worker_lab.now)
    worker_lab.db.refresh(zero_job)
    assert zero_job.state == "succeeded"
    assert zero_job.entries[0].count_added == zero_job.entries[0].count_updated == 0


def test_network_phase_allows_independent_database_writer(worker_lab, now):
    """入口running提交后网络阶段不持SQLite事务，另一个连接可以提交独立写入。"""
    job = worker_lab.pending_job(entries=1)
    worker_lab.succeed(0)
    base_factory = worker_lab.client_factory

    class CheckingClient:
        def __init__(self, base):
            self.base = base

        def fetch(self, url):
            with Session(worker_lab.db.bind) as observer:
                observer.add(Source(key="during-network", name="UNIT_ONLY network writer"))
                observer.commit()
            return self.base.fetch(url)

    process_job(worker_lab.db, claim_next(worker_lab.db, now),
                lambda entry: CheckingClient(base_factory(entry)), worker_lab.now)
    worker_lab.db.refresh(job)
    assert job.state == "succeeded"
    assert worker_lab.db.scalar(select(Source).where(Source.key == "during-network")) is not None


def test_restart_settles_running_not_pending(db, job_factory, article_factory, now):
    """旧running释放活动键，只改未完成结果；正常pending和既有阅读数据保持。"""
    from app.models import Bookmark

    article = article_factory()
    db.add(Bookmark(article_id=article.id, created_at=now))
    db.commit()
    old = job_factory(state="running", result_states=["succeeded", "failed", "running", "pending"])
    old.entries[0].count_added = 2
    old.entries[1].count_updated = 1
    old.entries[1].error = "先前失败"
    db.commit()
    assert settle_interrupted(db, now) == 1
    db.refresh(old)
    assert old.state == "interrupted" and old.finished_at == now
    assert [result.state for result in old.entries] == [
        "succeeded", "failed", "interrupted", "interrupted",
    ]
    assert old.entries[0].count_added == 2
    assert old.entries[1].count_updated == 1
    assert old.entries[1].error == "先前失败"
    assert db.get(type(article), article.id) is not None
    assert db.get(Bookmark, article.id) is not None

    queued = job_factory(state="pending")
    assert settle_interrupted(db, now) == 0
    db.refresh(queued)
    assert queued.state == "pending"
    assert settle_interrupted(db, now) == 0


def test_single_worker_and_application_locks_are_released(tmp_path):
    """本机真实文件锁拒绝第二持有者，退出后可重新取得；Linux分支仍待容器实测。"""
    worker_path = tmp_path / "worker.lock"
    with single_worker_lock(worker_path):
        with pytest.raises(RuntimeError):
            with single_worker_lock(worker_path):
                pass
    with single_worker_lock(worker_path):
        pass

    lease_path = tmp_path / "application.lock"
    with application_lease(lease_path, exclusive=False):
        with pytest.raises(RuntimeError):
            with application_lease(lease_path, exclusive=True):
                pass
    with application_lease(lease_path, exclusive=True):
        pass
