"""首次登录、会话读取和退出路由；登录前与登录后写保护明确分离。"""

from dataclasses import dataclass
import hmac
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session as DatabaseSession

from .auth import (
    AuthOut,
    LoginLimiter,
    client_address,
    csrf_token,
    issue_session,
    resolve_session,
    revoke_session,
    verify_password,
)
from .config import Settings
from .database import get_db
from .errors import ApiError
from .models import Session


class LoginIn(BaseModel):
    """首次登录只接受一个有界密码字段，拒绝额外输入。"""

    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=1024, repr=False)


@dataclass(frozen=True)
class AuthenticatedSession:
    """当前请求的服务端会话与一次性 Cookie 原文；不存入日志或响应。"""

    record: Session
    raw_token: str


def require_origin(request: Request, settings: Settings) -> None:
    """写操作只接受浏览器提供的精确同源 Origin，不信任 Host 或代理头替代。"""
    if request.headers.get("origin") != settings.public_origin:
        raise ApiError("origin_denied", "请求来源不被允许", 403)


def require_session(
    request: Request,
    db: DatabaseSession = Depends(get_db),
) -> AuthenticatedSession:
    """从安全 Cookie 解析当前会话；每次请求以服务器记录为准。"""
    raw = request.cookies.get("bi_session")
    record = resolve_session(db, raw, request.app.state.settings, request.app.state.now())
    return AuthenticatedSession(record=record, raw_token=raw or "")


def require_write(
    request: Request,
    authenticated: AuthenticatedSession = Depends(require_session),
) -> AuthenticatedSession:
    """登录后的写操作先有有效会话，再校验 Origin 与会话绑定的 CSRF。"""
    settings = request.app.state.settings
    require_origin(request, settings)
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = csrf_token(authenticated.raw_token, settings.csrf_key)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ApiError("csrf_invalid", "请求防护标记无效", 403)
    return authenticated


def _boundary_error(status: int, code: str, message: str) -> JSONResponse:
    """在 FastAPI 解析请求体前返回同样的脱敏错误结构。"""
    request_id = uuid4().hex
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "request_id": request_id},
        headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
    )


def install_login_boundary(app: FastAPI) -> None:
    """在首登 JSON 解析前限制来源、媒体类型和请求大小；不要求旧会话。"""

    @app.middleware("http")
    async def login_boundary(request: Request, call_next):
        if request.method == "POST" and request.url.path == "/api/auth/login":
            settings: Settings = request.app.state.settings
            if request.headers.get("origin") != settings.public_origin:
                return _boundary_error(403, "origin_denied", "请求来源不被允许")
            media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                return _boundary_error(415, "json_required", "登录请求必须使用 JSON")
            declared = request.headers.get("content-length")
            if declared:
                try:
                    if int(declared) > 16 * 1024:
                        return _boundary_error(413, "request_too_large", "登录请求过大")
                except ValueError:
                    return _boundary_error(400, "bad_request", "请求格式无效")
            body = await request.body()
            if len(body) > 16 * 1024:
                return _boundary_error(413, "request_too_large", "登录请求过大")
        return await call_next(request)


auth_router = APIRouter()


@auth_router.post("/api/auth/login", name="auth_login", response_model=AuthOut)
def login(request: Request, body: LoginIn, db: DatabaseSession = Depends(get_db)):
    """建立会话前校验来源、限流和密码；首次登录不消费旧 CSRF。"""
    settings: Settings = request.app.state.settings
    now = request.app.state.now()
    limiter: LoginLimiter = request.app.state.login_limiter
    address = client_address(request, settings)
    limiter.check(address, now)
    if not verify_password(body.password, settings.password_hash):
        limiter.failed(address, now)
        raise ApiError("invalid_credentials", "密码或登录信息无效", 401)
    raw, result = issue_session(db, settings, now)
    response = JSONResponse(result.model_dump(mode="json"))
    response.set_cookie(
        "bi_session", raw, max_age=86400, path="/", secure=True,
        httponly=True, samesite="strict",
    )
    return response


@auth_router.get("/api/auth/session", name="auth_session", response_model=AuthOut)
def current_session(
    request: Request,
    authenticated: AuthenticatedSession = Depends(require_session),
):
    """返回当前会话的稳定 CSRF 和服务器到期时间，不旋转 Cookie。"""
    return AuthOut(
        expires_at=authenticated.record.expires_at,
        csrf_token=csrf_token(authenticated.raw_token, request.app.state.settings.csrf_key),
    )


@auth_router.post("/api/auth/logout", name="auth_logout")
def logout(
    db: DatabaseSession = Depends(get_db),
    authenticated: AuthenticatedSession = Depends(require_write),
):
    """删除当前摘要并按相同 Cookie 路径清理浏览器会话。"""
    revoke_session(db, authenticated.raw_token)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie("bi_session", path="/", secure=True, httponly=True, samesite="strict")
    return response


def mount_router(app: FastAPI, router: APIRouter) -> None:
    """直接注册实际路由，不引入动态 registry 或插件体系。"""
    app.include_router(router)
