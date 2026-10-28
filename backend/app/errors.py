"""固定且脱敏的 JSON 错误边界；原始请求、异常正文和凭据不出现在响应中。"""

from uuid import uuid4
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """服务端可解释的失败；状态、机器码和安全文案分开传递。"""

    def __init__(self, code: str, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _result(request: Request, status: int, code: str, message: str) -> JSONResponse:
    """只返回与错误处理相关的固定字段，并阻止浏览器缓存错误。"""
    request_id = getattr(request.state, "request_id", uuid4().hex)
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "request_id": request_id},
        headers={"Cache-Control": "no-store"},
    )


def install_errors(app: FastAPI) -> None:
    """覆盖服务、参数、框架及意外异常，保证单一安全错误包。"""

    @app.middleware("http")
    async def request_identifier(request: Request, call_next):
        """为每个请求生成服务端标识；不信任客户端伪造的追踪头。"""
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/api/"):
            # 会话、CSRF和个人标题以服务器当前状态为准，成功响应也不得进入浏览器缓存。
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ApiError)
    async def known_error(request: Request, error: ApiError) -> JSONResponse:
        """返回已审定的业务失败，不回显请求内容。"""
        return _result(request, error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        """统一无效参数响应，避免 Pydantic 把输入值写进浏览器错误包。"""
        return _result(request, 400, "bad_request", "请求参数无效")

    @app.exception_handler(StarletteHTTPException)
    async def unknown_route(request: Request, error: StarletteHTTPException) -> JSONResponse:
        """无匹配路径或方法也遵守 API 错误包，不返回框架 detail。"""
        if error.status_code == 404:
            return _result(request, 404, "not_found", "页面或资源不存在")
        if error.status_code == 405:
            return _result(request, 405, "method_not_allowed", "不支持此操作")
        return _result(request, error.status_code, "http_error", "请求未完成")

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        """数据库不可读写统一返回安全503；请求依赖负责回滚并关闭会话。"""
        request_id = getattr(request.state, "request_id", None) or uuid4().hex
        request.state.request_id = request_id
        logging.getLogger("beauty_intelligence.errors").error(
            "storage_failed request_id=%s exception_type=%s",
            request_id,
            type(error).__name__,
        )
        return _result(request, 503, "storage_unavailable", "存储暂不可用")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        """未知异常隐藏异常值和堆栈，仅返回服务端错误类别。"""
        request_id = getattr(request.state, "request_id", None) or uuid4().hex
        request.state.request_id = request_id
        # 只记录异常类型与关联标识；异常正文和 exc_info 可能携带私密输入。
        logging.getLogger("beauty_intelligence.errors").error(
            "request_failed request_id=%s exception_type=%s",
            request_id,
            type(error).__name__,
        )
        return _result(request, 500, "internal_error", "服务暂不可用")
