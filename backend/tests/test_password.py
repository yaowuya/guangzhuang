"""密码验证与登录尝试边界；所有口令和地址均为单元测试输入。"""

import pytest
from argon2 import PasswordHasher

from app.auth import LoginLimiter, verify_password
from app.errors import ApiError


def test_argon_and_limits(now):
    """只接受正确的 Argon2id 密码，五次失败后本地址被限制。"""
    encoded = PasswordHasher().hash("test-only-secret")
    assert verify_password("test-only-secret", encoded)
    assert not verify_password("wrong", encoded)
    assert not verify_password("test-only-secret", "test-only-secret")
    assert not verify_password("test-only-secret", "$argon2id$invalid")
    limiter = LoginLimiter()
    for _ in range(5):
        limiter.check("203.0.113.1", now)
        limiter.failed("203.0.113.1", now)
    with pytest.raises(ApiError, match="尝试过多"):
        limiter.check("203.0.113.1", now)


def test_login_windows_expire_and_global_quota_is_atomic(now):
    """线程竞争不能多消耗全局配额，窗口结束后允许新的尝试。"""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta

    limiter = LoginLimiter()

    def attempt(index):
        try:
            limiter.check(f"203.0.113.{index + 1}", now)
            return True
        except ApiError as error:
            assert error.status == 429
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(50))) == 30
    limiter.check("203.0.113.1", now + timedelta(minutes=1))
    for _ in range(5):
        limiter.failed("203.0.113.1", now)
    with pytest.raises(ApiError):
        limiter.check("203.0.113.1", now + timedelta(minutes=14))
    limiter.check("203.0.113.1", now + timedelta(minutes=15))


def test_client_address_only_trusts_the_configured_gateway(settings):
    """伪造转发头不改变地址限流身份，可信 peer 的专用头也须为单个合法 IP。"""
    from dataclasses import replace
    from starlette.requests import Request
    from app.auth import client_address

    configured = replace(settings, trusted_gateway_ip="172.30.0.2")

    def request(peer, claimed):
        return Request({"type": "http", "client": (peer, 5000),
                        "headers": [(b"x-bi-client-ip", claimed.encode()),
                                    (b"x-forwarded-for", b"203.0.113.99")]})

    assert client_address(request("203.0.113.8", "203.0.113.9"), configured) == "203.0.113.8"
    assert client_address(request("172.30.0.2", "203.0.113.9"), configured) == "203.0.113.9"
    assert client_address(request("172.30.0.2", "203.0.113.9,203.0.113.10"), configured) == "172.30.0.2"
