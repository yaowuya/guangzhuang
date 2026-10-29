"""独立进程中断、跨连接阅读与当天恢复的持久化集成证据。"""

from pathlib import Path
import subprocess
import sys
import time

import pytest
from sqlalchemy.exc import OperationalError

from app.application.articles import upsert_headline
from app.domain.articles import Headline
from app.application.jobs import enqueue
from app.infrastructure.persistence.models import Article
from app.application.scheduling import catchup_due
from app.application.sources import apply_verification, eligible_entries, seed_sources
from app.infrastructure.configuration import load_registry
from app.runtime.worker import settle_interrupted


_PAUSED_WORKER = r'''
from datetime import datetime
from pathlib import Path
import sys, time
from app.infrastructure.persistence.database import db_session, make_engine
from app.infrastructure.http.safe_client import Fetched
from app.runtime.worker import claim_next, process_job

url, source_config, rules_config, now_value, ready_path, release_path = sys.argv[1:]
class PausedClient:
    def fetch(self, ignored_url):
        Path(ready_path).write_text("ready", encoding="utf-8")
        while not Path(release_path).exists():
            time.sleep(0.05)
        return Fetched(final_url="https://unit.example/feed", media_type="application/rss+xml",
                       body=b"<rss><channel></channel></rss>")
engine = make_engine(url)
try:
    with db_session(engine) as db:
        db.info.update(source_config=Path(source_config), rules_config=Path(rules_config))
        now = datetime.fromisoformat(now_value)
        job = claim_next(db, now)
        if job is None:
            raise RuntimeError("UNIT_ONLY missing pending job")
        process_job(db, job, lambda entry: PausedClient(), lambda: now)
finally:
    engine.dispose()
'''


def approve_two_entries(db, settings, now):
    settings.source_config.write_text(Path("config/sources.json").read_text(encoding="utf-8"), encoding="utf-8")
    settings.rules_config.write_text(Path("config/classification.json").read_text(encoding="utf-8"), encoding="utf-8")
    db.info.update(source_config=settings.source_config, rules_config=settings.rules_config)
    specs = load_registry(settings.source_config)
    seed_sources(db, specs)
    for key in ("prtimes-rss", "happi-rss"):
        spec = next(item for item in specs if item.key == key)
        apply_verification(db, {
            "entry_key": key, "verification_status": "allowed",
            "verification_reason": "UNIT_ONLY recovery许可", "verification_reference": "unit-reference",
            "automation_allowed": True, "title_storage_allowed": True,
        }, {
            "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
            "title_count": 1, "final_url": spec.url, "error": None,
        }, now)
    return eligible_entries(db)


def test_reading_survives_interrupted_update(
    db, settings, user_client, now, caplog, tmp_path,
):
    """网络暂停/kill时旧阅读可用；重启只中断未完成入口并补该入口。"""
    entries = approve_two_entries(db, settings, now)
    stored = upsert_headline(db, Headline(
        entries[0].source_id, entries[0].id,
        "https://example.org/already-committed", "已提交且仍可阅读的标题",
    ), now)
    db.commit()
    old_article = db.get(Article, stored.article_id)
    assert user_client.put(f"/api/bookmarks/{old_article.id}", json={}).status_code == 200
    scheduled = enqueue(db, "schedule", [entry.id for entry in entries], now.date(), now).job
    scheduled.entries[0].state = "succeeded"
    scheduled.entries[0].count_added = 1
    scheduled.entries[0].finished_at = now
    db.commit()
    old_id = scheduled.id
    unfinished = scheduled.entries[1].entry_id

    ready, release = tmp_path / "network-ready", tmp_path / "network-release"
    process = subprocess.Popen(
        [sys.executable, "-c", _PAUSED_WORKER, settings.database_url,
         str(settings.source_config), str(settings.rules_config), now.isoformat(),
         str(ready), str(release)],
        cwd=Path(__file__).resolve().parents[3],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if not ready.exists():
            stdout, stderr = process.communicate(timeout=5)
            pytest.fail(f"子进程未进入合成网络等待: {stdout!r} {stderr!r}")
        response = user_client.get(f"/api/articles/{old_article.id}")
        assert response.status_code == 200 and response.json()["bookmarked"] is True
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        assert "CONTENT_SENTINEL" not in stdout + stderr
    finally:
        release.write_text("release", encoding="utf-8")
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)

    db.expire_all()
    assert settle_interrupted(db, now) == 1
    recovered = catchup_due(db, now)
    assert recovered is not None and old_id != recovered.job.id
    assert {result.entry_id for result in recovered.job.entries} == {unfinished}
    assert any(record.message == "job_interrupted" and record.job_id == old_id
               for record in caplog.records)
    assert user_client.get(f"/api/articles/{old_article.id}").json()["bookmarked"] is True


def test_failed_settlement_does_not_emit_success_event(db, job_factory, now, caplog, monkeypatch):
    """提交失败时回滚running状态且不能预先记录job_interrupted审计事件。"""
    job = job_factory(state="running", result_states=["running"])
    original_commit = db.commit

    def fail_commit():
        raise OperationalError("unit settlement", {}, RuntimeError("DISK_FULL_SENTINEL"))

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(OperationalError):
        settle_interrupted(db, now)
    monkeypatch.setattr(db, "commit", original_commit)
    db.refresh(job)
    assert job.state == "running"
    assert not any(record.message == "job_interrupted" for record in caplog.records)
