"""同一 FastAPI 进程提供已构建前端，同时保持 /api JSON 边界。"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def built_frontend(tmp_path):
    """构造隔离的 SPA 入口、脚本和普通文件，供真实 HTTP 适配测试读取。"""
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text('<div id="app">frontend-shell</div>', encoding="utf-8")
    (root / "assets/app.js").write_text("console.log('asset-sentinel')", encoding="utf-8")
    (root / "robots.txt").write_text("User-agent: *\nDisallow: /", encoding="utf-8")
    return root


def test_serves_assets_files_and_spa_without_swallowing_api(settings, tmp_path):
    """页面与文件可读，API 的 404/405 和缺失资产的错误语义不被 SPA 吞掉。"""
    static = built_frontend(tmp_path)
    app = create_app(replace(settings, static_dir=static))

    with TestClient(app, base_url="https://unit.example", raise_server_exceptions=False) as client:
        assert "frontend-shell" in client.get("/").text
        assert "frontend-shell" in client.get("/favorites?q=lip").text
        assert client.get("/assets/app.js").text == "console.log('asset-sentinel')"
        assert client.get("/robots.txt").text.startswith("User-agent")
        assert client.head("/favorites").status_code == 200

        api_root = client.get("/api")
        assert api_root.status_code == 404
        assert api_root.json()["code"] == "not_found"
        assert "frontend-shell" not in api_root.text

        missing_api = client.get("/api/not-real")
        assert missing_api.status_code == 404
        assert missing_api.json()["code"] == "not_found"
        assert missing_api.headers["cache-control"] == "no-store"
        assert "frontend-shell" not in missing_api.text
        assert client.post("/api/not-real").status_code == 404
        assert client.post("/api/articles").status_code == 405

        for missing_file in ("/assets/missing.js", "/assets/missing", "/favicon.ico"):
            response = client.get(missing_file)
            assert response.status_code == 404
            assert "frontend-shell" not in response.text


def test_static_frontend_rejects_escape_and_missing_build(settings, tmp_path):
    """路径逃逸请求不能读取外部文件，缺少前端入口时应用拒绝构造。"""
    static = built_frontend(tmp_path)
    app = create_app(replace(settings, static_dir=static))
    with TestClient(app, base_url="https://unit.example", raise_server_exceptions=False) as client:
        escaped = client.get("/%2e%2e/backend/pyproject.toml")
        assert escaped.status_code == 404
        assert "frontend-shell" not in escaped.text

    with pytest.raises(ValueError, match="index.html"):
        create_app(replace(settings, static_dir=tmp_path / "missing"))
