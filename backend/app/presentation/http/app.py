"""FastAPI 应用构造入口；导入不读取来源或启动定时任务。"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.presentation.http.articles import articles_router
from app.presentation.http.auth import auth_router, install_login_boundary, mount_router
from app.presentation.http.bookmarks import bookmarks_router
from app.presentation.http.jobs import jobs_router
from app.presentation.http.sources import sources_router
from app.presentation.http.static_frontend import install_frontend
from app.application.auth import LoginLimiter
from app.core.config import Settings
from app.infrastructure.persistence.database import application_lease
from app.presentation.http.errors import install_errors


def create_app(settings: Settings | None = None) -> FastAPI:
    """构造同源应用；缺正式私密配置时拒绝运行，不在导入阶段联网或迁移数据库。"""
    resolved = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """整个API进程持共享租约，离线恢复无法与请求处理并发覆盖数据库。"""
        with application_lease(resolved.data_dir / "application.lock", exclusive=False):
            yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings = resolved
    app.state.now = lambda: datetime.now(UTC)
    app.state.login_limiter = LoginLimiter()
    install_errors(app)
    install_login_boundary(app)
    mount_router(app, auth_router)
    mount_router(app, articles_router)
    mount_router(app, bookmarks_router)
    mount_router(app, sources_router)
    mount_router(app, jobs_router)
    install_frontend(app, resolved.static_dir)
    return app
