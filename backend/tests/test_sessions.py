"""真实临时 SQLite 中的会话签发、到期与撤销；不伪造生产 Cookie。"""

from datetime import timedelta
import pytest

from app.auth import issue_session, resolve_session, csrf_token, revoke_session
from app.errors import ApiError


def test_expiry_csrf_and_revoke(db, settings, now):
    """同令牌查询不旋转标记，24 小时边界拒绝且撤销立即生效。"""
    raw, auth = issue_session(db, settings, now)
    assert auth.expires_at == now + timedelta(hours=24)
    assert auth.csrf_token == csrf_token(raw, settings.csrf_key)
    assert resolve_session(db, raw, settings, now).token_digest != raw
    with pytest.raises(ApiError) as expired:
        resolve_session(db, raw, settings, now + timedelta(hours=24))
    assert expired.value.status == 401
    revoke_session(db, raw)
    with pytest.raises(ApiError):
        resolve_session(db, raw, settings, now)


def test_random_tokens_are_not_stored_and_revocation_is_visible_to_new_connection(db, settings, now):
    """不同签发不同令牌，另一数据库会话立即观察到撤销；DB dump 不含原凭据。"""
    from sqlalchemy import select
    from sqlalchemy.orm import Session as DatabaseSession
    from app.models import Session

    first, first_auth = issue_session(db, settings, now)
    second, _ = issue_session(db, settings, now)
    assert first != second
    assert csrf_token(first, settings.csrf_key) == first_auth.csrf_token
    assert first_auth.csrf_token not in repr(first_auth)
    rows = db.scalars(select(Session)).all()
    assert len(rows) == 2
    assert all(row.token_digest not in {first, second} for row in rows)
    assert resolve_session(db, first, settings, now + timedelta(hours=23, minutes=59))
    revoke_session(db, first)
    revoke_session(db, first)
    with DatabaseSession(db.bind) as observer:
        with pytest.raises(ApiError):
            resolve_session(observer, first, settings, now)
        assert resolve_session(observer, second, settings, now)


@pytest.mark.parametrize("raw", [None, "", "unknown-token", "a" * 257])
def test_invalid_tokens_are_uniformly_rejected(db, settings, now, raw):
    """没有会话与随机输入使用同一个拒绝状态，避免暴露内部判断细节。"""
    with pytest.raises(ApiError) as error:
        resolve_session(db, raw, settings, now)
    assert (error.value.status, error.value.code) == (401, "unauthenticated")
