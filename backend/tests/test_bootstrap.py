"""应用导入、私密配置与安全错误的首个公开接缝测试。"""

from fastapi.testclient import TestClient
import pytest
import subprocess
import sys

from app.errors import ApiError
from app.main import create_app


def test_factory_and_safe_errors(settings):
    """调用方只看固定脱敏错误包，而非框架或异常堆栈。"""
    app = create_app(settings)

    @app.get("/test-error")
    def fail():
        raise ApiError("storage_unavailable", "存储暂不可用", 503)

    response = TestClient(
        app,
        base_url=settings.public_origin,
        raise_server_exceptions=False,
    ).get("/test-error")
    assert response.status_code == 503
    assert set(response.json()) == {"code", "message", "request_id"}
    assert response.json()["code"] == "storage_unavailable"
    assert response.json()["request_id"]


def test_unexpected_error_is_redacted(settings, caplog):
    """异常正文、栈与私密细节不得返回给浏览器。"""
    app = create_app(settings)

    @app.get("/test-crash")
    def crash():
        raise RuntimeError("UNIT_ONLY_PRIVATE_MARKER")

    response = TestClient(
        app,
        base_url=settings.public_origin,
        raise_server_exceptions=False,
    ).get("/test-crash")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert set(response.json()) == {"code", "message", "request_id"}
    assert "PRIVATE_MARKER" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" in caplog.text
    assert response.json()["request_id"] in caplog.text
    assert "PRIVATE_MARKER" not in caplog.text


def test_framework_not_found_and_wrong_method_are_safe(settings):
    """未注册路由和方法同样返回固定错误结构，不泄漏框架的 detail 包。"""
    app = create_app(settings)

    @app.get("/known")
    def known():
        return {"ok": True}

    client = TestClient(app, base_url=settings.public_origin, raise_server_exceptions=False)
    missing = client.get("/unregistered")
    wrong_method = client.post("/known")
    assert missing.status_code == 404
    assert wrong_method.status_code == 405
    assert missing.json()["code"] == "not_found"
    assert wrong_method.json()["code"] == "method_not_allowed"
    assert set(missing.json()) == {"code", "message", "request_id"}
    assert set(wrong_method.json()) == {"code", "message", "request_id"}


def test_validation_errors_hide_input_and_ignore_client_request_id(settings):
    """参数校验不泄露原值，客户端提供的关联标识不能冒充服务器标识。"""
    app = create_app(settings)

    @app.get("/typed")
    def typed(count: int):
        return {"count": count}

    client = TestClient(app, base_url=settings.public_origin)
    response = client.get(
        "/typed", params={"count": "UNIT_SECRET_SENTINEL"},
        headers={"X-Request-ID": "caller-controlled"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "bad_request"
    assert "UNIT_SECRET_SENTINEL" not in response.text
    assert response.json()["request_id"] != "caller-controlled"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert response.headers["Cache-Control"] == "no-store"


def test_missing_private_settings_reject_startup(monkeypatch):
    """无明示来源域名与密钥时启动失败，而不是默认使用测试口令。"""
    from app.config import Settings

    for key in ("PUBLIC_ORIGIN", "PASSWORD_HASH_FILE", "CSRF_KEY_FILE"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError):
        Settings.from_environment()


def test_import_does_not_connect_to_network_or_database():
    """新进程导入必须纯粹；启动工厂才读取部署配置。"""
    statement = """
import socket
import sqlite3

def forbidden(*args, **kwargs):
    raise AssertionError('IMPORT_SIDE_EFFECT')

socket.socket.connect = forbidden
sqlite3.connect = forbidden
import app.main
"""
    result = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_settings_repr_does_not_disclose_credentials(settings):
    """诊断配置对象时不能无意打印服务端私密值。"""
    rendered = repr(settings)
    assert settings.password_hash not in rendered
    assert settings.csrf_key not in rendered


def test_private_files_are_required_and_hash_must_be_valid(monkeypatch, tmp_path, settings):
    """不接受看似有前缀但不可验证的密码摘要，正确文件无需创建数据目录。"""
    from app.config import Settings

    password_file = tmp_path / "password.hash"
    csrf_file = tmp_path / "csrf.key"
    password_file.write_text(settings.password_hash, encoding="utf-8")
    csrf_file.write_text(settings.csrf_key, encoding="utf-8")
    monkeypatch.setenv("PUBLIC_ORIGIN", settings.public_origin)
    monkeypatch.setenv("PASSWORD_HASH_FILE", str(password_file))
    monkeypatch.setenv("CSRF_KEY_FILE", str(csrf_file))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "uncreated-data"))
    actual = Settings.from_environment()
    assert actual.public_origin == "https://unit.example"
    assert not actual.data_dir.exists()
    password_file.write_text("$argon2id$invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        Settings.from_environment()
