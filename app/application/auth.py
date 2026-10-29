"""单人服务密码与会话保护；不提供注册、团队或后台管理身份。"""

from collections import deque
from datetime import datetime, timedelta
from threading import Lock
from typing import Literal
import hashlib
import hmac
import secrets

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DatabaseSession

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from app.core.config import Settings
from app.core.exceptions import ApiError
from app.infrastructure.persistence.models import Session


class AuthOut(BaseModel):
    """当前已确认的服务器会话；CSRF 仅返回给已登录页面，不进入日志 repr。"""

    authenticated: Literal[True] = True
    expires_at: datetime
    csrf_token: str = Field(repr=False)


def csrf_token(raw: str, key: str) -> str:
    """按会话令牌稳定派生 HMAC，多页面会话查询不使其它页面标记失效。"""
    return hmac.new(key.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_session(db: DatabaseSession, settings: Settings, now: datetime) -> tuple[str, AuthOut]:
    """提交会话摘要后返回原令牌与响应；数据库永不保存原令牌或 HMAC 密钥。"""
    raw = secrets.token_urlsafe(32)
    expires = now + timedelta(hours=24)
    db.add(Session(token_digest=hashlib.sha256(raw.encode()).hexdigest(),
                   created_at=now, expires_at=expires))
    db.commit()
    return raw, AuthOut(expires_at=expires, csrf_token=csrf_token(raw, settings.csrf_key))


def resolve_session(db: DatabaseSession, raw: str | None, settings: Settings, now: datetime) -> Session:
    """每次请求查服务器记录；不存在或到期统一拒绝，不凭客户端状态续期。"""
    if not raw or len(raw) > 256:
        raise ApiError("unauthenticated", "请先登录", 401)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    session = db.scalar(select(Session).where(Session.token_digest == digest))
    if session is None or session.expires_at <= now:
        raise ApiError("unauthenticated", "请先登录", 401)
    return session


def revoke_session(db: DatabaseSession, raw: str) -> None:
    """删除摘要记录完成即时撤销；重复撤销不创建状态或恢复旧会话。"""
    digest = hashlib.sha256(raw.encode()).hexdigest()
    db.execute(delete(Session).where(Session.token_digest == digest))
    db.commit()


def verify_password(password: str, encoded: str) -> bool:
    """只验证部署提供的 Argon2id 摘要；不保存或记录原口令。"""
    if not encoded.startswith("$argon2id$"):
        return False
    try:
        return PasswordHasher().verify(encoded, password)
    except (InvalidHashError, VerificationError):
        return False


class LoginLimiter:
    """单 API 实例中的有界尝试窗口；进程重启重置，不声称永久或分布式封禁。"""

    def __init__(self) -> None:
        self._attempts: deque[datetime] = deque()
        self._failures: dict[str, deque[datetime]] = {}
        self._lock = Lock()

    def _prune(self, now: datetime) -> None:
        while self._attempts and self._attempts[0] <= now - timedelta(minutes=1):
            self._attempts.popleft()
        for address in list(self._failures):
            failures = self._failures[address]
            while failures and failures[0] <= now - timedelta(minutes=15):
                failures.popleft()
            if not failures:
                del self._failures[address]

    def check(self, client_ip: str, now: datetime) -> None:
        """原子检查并计入全局尝试；一个地址五次失败或每分钟三十次总尝试后拒绝。"""
        with self._lock:
            self._prune(now)
            if len(self._attempts) >= 30:
                raise ApiError("rate_limited", "登录尝试过多，请稍后再试", 429)
            self._attempts.append(now)
            if len(self._failures.get(client_ip, ())) >= 5:
                raise ApiError("rate_limited", "登录尝试过多，请稍后再试", 429)

    def failed(self, client_ip: str, now: datetime) -> None:
        """只记录检查过的失败尝试；成功不会删除仍在窗口内的失败记录。"""
        with self._lock:
            self._prune(now)
            self._failures.setdefault(client_ip, deque()).append(now)
