"""仅提供隔离测试环境，不导入真实来源、部署密码或生产数据。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient


@pytest.fixture
def now() -> datetime:
    """提供可复现的 UTC 时间；不依赖测试机本地时区。"""
    return datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path: Path):
    """生成仅供本次测试使用的配置；凭据不落仓库或日志。"""
    from app.config import Settings

    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
        public_origin="https://unit.example",
        password_hash=PasswordHasher().hash("unit-password"),
        csrf_key="unit-only-csrf-key-not-a-production-secret",
        source_config=tmp_path / "sources.json",
        rules_config=tmp_path / "classification.json",
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        trusted_gateway_ip="",
    )


@pytest.fixture
def client(settings):
    """在 HTTPS 测试入口观察公开响应，不伪造业务来源。"""
    from app.main import create_app

    return TestClient(
        create_app(settings),
        base_url=settings.public_origin,
        raise_server_exceptions=False,
    )
