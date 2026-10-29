"""更新任务创建、重试、当前与详情的 HTTP 契约测试。"""

from pathlib import Path

from sqlalchemy import select

from app.infrastructure.persistence.models import UpdateJob
from app.application.sources import apply_verification, seed_sources
from app.infrastructure.configuration import load_registry


def configure_sources(db, settings, now, allowed=False):
    """准备固定本地候选，可选用合成证据启用一个入口。"""
    settings.source_config.write_text(Path("config/sources.json").read_text(encoding="utf-8"), encoding="utf-8")
    db.info["source_config"] = settings.source_config
    specs = load_registry(settings.source_config)
    seed_sources(db, specs)
    if allowed:
        spec = next(item for item in specs if item.key == "prtimes-rss")
        apply_verification(db, {
            "entry_key": spec.key, "verification_status": "allowed",
            "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
            "automation_allowed": True, "title_storage_allowed": True,
        }, {
            "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
            "title_count": 1, "final_url": spec.url, "error": None,
        }, now)


def test_job_routes_and_null_current(user_client, db, settings, now):
    """无记录明确null；无入口409；首次入队202，活动复用200且current稳定。"""
    configure_sources(db, settings, now, allowed=False)
    assert user_client.get("/api/update-jobs/current").json() == {"job": None}
    assert user_client.post("/api/update-jobs", json={"trigger": "refresh"}).status_code == 409
    configure_sources(db, settings, now, allowed=True)
    first = user_client.post("/api/update-jobs", json={"trigger": "refresh"})
    assert first.status_code == 202 and first.json()["reused"] is False
    again = user_client.post("/api/update-jobs", json={"trigger": "refresh"})
    assert again.status_code == 200 and again.json()["reused"] is True
    assert again.json()["job"]["id"] == first.json()["job"]["id"]
    current = user_client.get("/api/update-jobs/current").json()["job"]
    assert current["id"] == first.json()["job"]["id"]
    assert set(current) == {
        "id", "trigger", "state", "schedule_date", "created_at", "started_at",
        "finished_at", "count_added", "count_updated", "entries",
    }
    assert current["entries"][0]["source_name"] == "PR TIMES"
    assert set(current["entries"][0]) == {
        "entry_id", "source_id", "source_name", "entry_url", "state",
        "count_added", "count_updated", "error", "finished_at",
    }
    assert current["created_at"].endswith("Z")


def test_job_detail_counts_and_retry_status_codes(user_client, db, settings, now):
    """详情按入口聚合计数；终态失败重试202，活动重试复用200。"""
    configure_sources(db, settings, now, allowed=True)
    created = user_client.post("/api/update-jobs", json={"trigger": "refresh"})
    job = db.get(UpdateJob, created.json()["job"]["id"])
    job.state = "failed"
    job.started_at = now
    job.finished_at = now
    job.entries[0].state = "failed"
    job.entries[0].count_added = 2
    job.entries[0].count_updated = 1
    job.entries[0].error = "UNIT_ONLY 访问失败"
    job.entries[0].finished_at = now
    db.commit()
    detail = user_client.get(f"/api/update-jobs/{job.id}")
    assert detail.status_code == 200
    assert (detail.json()["count_added"], detail.json()["count_updated"]) == (2, 1)
    first_retry = user_client.post(f"/api/update-jobs/{job.id}/retry", json={})
    assert first_retry.status_code == 202
    assert first_retry.json()["job"]["trigger"] == "retry"
    reused = user_client.post(f"/api/update-jobs/{job.id}/retry", json={})
    assert reused.status_code == 200 and reused.json()["reused"] is True


def test_job_routes_validate_auth_csrf_payload_and_missing_ids(client, settings, db, now):
    """读取需会话，写需Origin/CSRF，非法trigger/额外字段400，不存在404。"""
    configure_sources(db, settings, now, allowed=True)
    assert client.get("/api/update-jobs/current").status_code == 401
    assert client.post("/api/update-jobs", json={"trigger": "refresh"}).status_code == 401
    logged = client.post("/api/auth/login", json={"password": "unit-password"},
                         headers={"Origin": settings.public_origin})
    csrf = logged.json()["csrf_token"]
    no_csrf = client.post("/api/update-jobs", json={"trigger": "refresh"},
                          headers={"Origin": settings.public_origin})
    assert (no_csrf.status_code, no_csrf.json()["code"]) == (403, "csrf_invalid")
    headers = {"Origin": settings.public_origin, "X-CSRF-Token": csrf}
    invalid = client.post("/api/update-jobs", json={"trigger": "schedule"}, headers=headers)
    extra = client.post("/api/update-jobs", json={"trigger": "refresh", "source": 1}, headers=headers)
    assert (invalid.status_code, extra.status_code) == (400, 400)
    missing = client.get("/api/update-jobs/999999")
    bad_id = client.get("/api/update-jobs/not-an-id")
    assert (missing.status_code, missing.json()["code"]) == (404, "job_not_found")
    assert (bad_id.status_code, bad_id.json()["code"]) == (400, "bad_request")
