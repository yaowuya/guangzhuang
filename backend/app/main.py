"""FastAPI 应用构造入口；导入不读取来源或启动定时任务。"""

from datetime import UTC, datetime

from fastapi import FastAPI

from .config import Settings
from .errors import install_errors


def create_app(settings: Settings | None = None) -> FastAPI:
    """构造同源应用；缺正式私密配置时拒绝运行，不在导入阶段联网或迁移数据库。"""
    resolved = settings if settings is not None else Settings.from_environment()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = resolved
    app.state.now = lambda: datetime.now(UTC)
    install_errors(app)
    return app
