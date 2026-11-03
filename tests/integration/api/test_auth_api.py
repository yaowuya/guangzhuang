"""同源首登、服务端会话与业务写保护的 HTTP 接缝测试。"""

import asyncio
from datetime import timedelta

import pytest


def login(client, settings, password="unit-password", **headers):
    """通过正式登录入口取得测试会话，不直接写会话表。"""
    return client.post(
        "/api/auth/login",
        json={"password": password},
        headers={"Origin": settings.public_origin, **headers},
    )


def test_first_login_and_write_guards(client, settings):
    """首次登录无需旧 CSRF；退出必须同时具有会话、Origin 和当前标记。"""
    response = login(client, settings)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert all(marker in cookie for marker in ("bi_session=", "HttpOnly", "Secure", "SameSite=strict", "Path=/"))
    assert "Domain=" not in cookie
    assert response.headers["Cache-Control"] == "no-store"
    csrf = response.json()["csrf_token"]
    session_response = client.get("/api/auth/session")
    assert session_response.json()["csrf_token"] == csrf
    assert session_response.headers["Cache-Control"] == "no-store"

    denied = client.post("/api/auth/logout", json={}, headers={"Origin": settings.public_origin})
    assert (denied.status_code, denied.json()["code"]) == (403, "csrf_invalid")
    confirmed = client.post("/api/auth/logout", json={}, headers={
        "Origin": settings.public_origin, "X-CSRF-Token": csrf,
    })
    assert confirmed.status_code == 200
    assert confirmed.json() == {"authenticated": False}
    assert "Max-Age=0" in confirmed.headers["set-cookie"]
    assert client.get("/api/auth/session").status_code == 401


@pytest.mark.parametrize(("kwargs", "status", "code"), [
    ({"headers": {"Origin": "https://outside.example"}, "json": {"password": "unit-password"}}, 403, "origin_denied"),
    ({"headers": {"Origin": "https://unit.example", "Content-Type": "text/plain"}, "content": "unit-password"}, 415, "json_required"),
    ({"headers": {"Origin": "https://unit.example"}, "json": {"password": "unit-password", "extra": True}}, 400, "bad_request"),
    ({"headers": {"Origin": "https://unit.example"}, "json": {"password": "wrong"}}, 401, "invalid_credentials"),
])
def test_login_rejects_invalid_boundaries(client, kwargs, status, code):
    """登录前校验不会回显密码、字段或框架 detail。"""
    response = client.post("/api/auth/login", **kwargs)
    assert (response.status_code, response.json()["code"]) == (status, code)
    assert set(response.json()) == {"code", "message", "request_id"}
    assert "unit-password" not in response.text
    assert "wrong" not in response.text


def test_chunked_login_body_stops_at_limit_before_full_buffering(settings):
    """无Content-Length的多chunk请求超过16KiB时立即413，不继续消费剩余载荷。"""
    from app.main import create_app

    application = create_app(settings)
    chunks = [b'{"password":"', b'x' * 9000, b'y' * 9000, b'z' * 9000]
    received = 0
    sent = []

    async def receive():
        nonlocal received
        chunk = chunks[received]
        received += 1
        return {"type": "http.request", "body": chunk, "more_body": received < len(chunks)}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "https", "path": "/api/auth/login",
        "raw_path": b"/api/auth/login", "query_string": b"", "root_path": "",
        "headers": [(b"origin", settings.public_origin.encode()),
                    (b"content-type", b"application/json")],
        "client": ("203.0.113.8", 5000), "server": ("unit.example", 443),
    }
    asyncio.run(application(scope, receive, send))
    response_start = next(message for message in sent if message["type"] == "http.response.start")
    assert response_start["status"] == 413
    assert received == 3


def test_login_body_limit_and_rate_limit(client, settings):
    """超大请求在 JSON 解析前拒绝，密码失败受两级限流。"""
    too_large = client.post(
        "/api/auth/login",
        content=b'{' + b'"password":"' + b'x' * 17000 + b'"}',
        headers={"Origin": settings.public_origin, "Content-Type": "application/json"},
    )
    assert (too_large.status_code, too_large.json()["code"]) == (413, "request_too_large")
    for _ in range(5):
        assert login(client, settings, "wrong").status_code == 401
    limited = login(client, settings, "wrong")
    assert (limited.status_code, limited.json()["code"]) == (429, "rate_limited")


def test_session_expiry_and_logout_failure_semantics(client, settings, now):
    """服务端时间达到 24 小时即失效；错误标记不会撤销或假报退出。"""
    logged_in = login(client, settings)
    csrf = logged_in.json()["csrf_token"]
    wrong = client.post("/api/auth/logout", json={}, headers={
        "Origin": settings.public_origin, "X-CSRF-Token": "wrong",
    })
    assert wrong.status_code == 403
    assert client.get("/api/auth/session").status_code == 200
    client.app.state.now = lambda: now + timedelta(hours=24)
    expired = client.get("/api/auth/session")
    assert (expired.status_code, expired.json()["code"]) == (401, "unauthenticated")
    assert client.post("/api/auth/logout", json={}, headers={
        "Origin": settings.public_origin, "X-CSRF-Token": csrf,
    }).status_code == 401
