"""收藏列表与幂等写接口的跨入口一致性测试。"""

from sqlalchemy.exc import OperationalError


def test_state_consistency_and_write_failure(user_client, article_factory, monkeypatch):
    """服务端确认后所有读取入口一致，失败取消不能抹除已有收藏。"""
    article = article_factory()
    response = user_client.put(f"/api/bookmarks/{article.id}", json={})
    assert response.json() == {"article_id": article.id, "bookmarked": True}
    assert user_client.get(f"/api/articles/{article.id}").json()["bookmarked"] is True
    assert user_client.get("/api/articles").json()["items"][0]["bookmarked"] is True
    assert user_client.get("/api/bookmarks").json()["items"][0]["bookmarked"] is True

    from app.presentation.http import bookmarks as api_bookmarks

    def storage_failure(*args, **kwargs):
        raise OperationalError("unit write", {}, RuntimeError("UNIT_ONLY"))

    monkeypatch.setattr(api_bookmarks, "set_bookmark", storage_failure)
    failed = user_client.delete(f"/api/bookmarks/{article.id}")
    assert (failed.status_code, failed.json()["code"]) == (503, "storage_unavailable")
    assert user_client.get(f"/api/articles/{article.id}").json()["bookmarked"] is True


def test_bookmark_permission_validation_and_idempotent_http_results(client, settings, article_factory):
    """匿名、缺标记和错误来源分别拒绝；成功写与重复取消返回同一布尔语义。"""
    article = article_factory()
    assert client.put(f"/api/bookmarks/{article.id}", json={}).status_code == 401
    logged = client.post("/api/auth/login", json={"password": "unit-password"},
                         headers={"Origin": settings.public_origin})
    csrf = logged.json()["csrf_token"]
    missing_csrf = client.put(f"/api/bookmarks/{article.id}", json={},
                              headers={"Origin": settings.public_origin})
    assert (missing_csrf.status_code, missing_csrf.json()["code"]) == (403, "csrf_invalid")
    wrong_origin = client.put(f"/api/bookmarks/{article.id}", json={}, headers={
        "Origin": "https://outside.example", "X-CSRF-Token": csrf,
    })
    assert (wrong_origin.status_code, wrong_origin.json()["code"]) == (403, "origin_denied")
    headers = {"Origin": settings.public_origin, "X-CSRF-Token": csrf}
    first = client.put(f"/api/bookmarks/{article.id}", json={}, headers=headers)
    repeated = client.put(f"/api/bookmarks/{article.id}", json={}, headers=headers)
    assert first.json() == repeated.json() == {"article_id": article.id, "bookmarked": True}
    assert client.delete(f"/api/bookmarks/{article.id}", headers=headers).json()["bookmarked"] is False
    assert client.delete(f"/api/bookmarks/{article.id}", headers=headers).json()["bookmarked"] is False
    assert client.get(f"/api/articles/{article.id}").json()["bookmarked"] is False


def test_bookmark_query_and_payload_errors_are_not_silently_accepted(user_client, article_factory):
    """非法筛选、额外写字段和不存在条目保持固定400/404。"""
    article = article_factory()
    assert user_client.get("/api/bookmarks", params=[("page", "1"), ("page", "2")]).status_code == 400
    extra = user_client.put(f"/api/bookmarks/{article.id}", json={"snapshot": True})
    assert (extra.status_code, extra.json()["code"]) == (400, "bad_request")
    missing = user_client.put("/api/bookmarks/999999", json={})
    assert (missing.status_code, missing.json()["code"]) == (404, "article_not_found")
