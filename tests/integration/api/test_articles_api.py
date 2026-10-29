"""已登录标题列表、详情与筛选 HTTP 白名单契约测试。"""

from datetime import date

from sqlalchemy.exc import OperationalError


def test_article_contract_and_filters(user_client, article_factory):
    """列表和详情只返回标题元信息、空值与服务端收藏标记。"""
    article = article_factory(reported_date=None, category_codes=[])
    response = user_client.get("/api/articles")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == article.id
    assert item["bookmarked"] is False
    assert item["source"] == {"id": article.source_id, "key": "unit", "name": "UNIT_ONLY 来源", "language": None}
    assert item["updated_at"].endswith("Z")
    assert set(item) == {
        "id", "title", "source", "original_url", "reported_date", "category_codes",
        "region", "product_type", "image_url", "image_credit", "updated_at", "bookmarked",
    }
    detail = user_client.get(f"/api/articles/{article.id}").json()
    assert detail["reported_date"] is None and detail["category_codes"] == []
    assert {"body", "summary", "event_id"}.isdisjoint(detail)
    assert user_client.get("/api/articles?page_size=101").status_code == 400
    options = user_client.get("/api/filters").json()
    assert len(options["categories"]) == 7
    assert options["uncategorized_value"] == "__uncategorized__"


def test_storage_errors_use_safe_service_unavailable_envelope(user_client, monkeypatch):
    """代表性读取发生SQLite错误时统一503，不泄露SQL或降级为未知500。"""
    from app.presentation.http import articles as api_articles

    def locked_storage(*args, **kwargs):
        raise OperationalError("SELECT PRIVATE_SQL_SENTINEL", {}, RuntimeError("locked"))

    monkeypatch.setattr(api_articles, "list_articles", locked_storage)
    response = user_client.get("/api/articles")
    assert (response.status_code, response.json()["code"]) == (503, "storage_unavailable")
    assert "PRIVATE_SQL_SENTINEL" not in response.text


def test_reading_routes_require_session(client):
    """匿名请求不能读取个人标题、筛选或不存在详情的差异。"""
    for path in ("/api/articles", "/api/articles/1", "/api/filters"):
        response = client.get(path)
        assert (response.status_code, response.json()["code"]) == (401, "unauthenticated")


def test_invalid_queries_and_missing_detail_use_fixed_errors(user_client, article_factory):
    """非法筛选不能放宽成全库；正整数 ID 不存在与类型错误分开。"""
    article_factory(reported_date=date(2026, 1, 1))
    invalid = [
        [("page", "1"), ("page", "2")], [("category", "not-a-category")],
        [("date_from", "2026-02-02"), ("date_to", "2026-02-01")],
        [("page", "0")], [("extra", "x")],
    ]
    for params in invalid:
        response = user_client.get("/api/articles", params=params)
        assert (response.status_code, response.json()["code"]) == (400, "invalid_filter")
    missing = user_client.get("/api/articles/999999")
    invalid_id = user_client.get("/api/articles/not-an-id")
    assert (missing.status_code, missing.json()["code"]) == (404, "article_not_found")
    assert (invalid_id.status_code, invalid_id.json()["code"]) == (400, "bad_request")
