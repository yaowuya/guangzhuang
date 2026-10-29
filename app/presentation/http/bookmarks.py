"""收藏列表与幂等写 API；成功响应只在 SQLite 提交后返回。"""

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DatabaseSession

from app.presentation.http.auth import AuthenticatedSession, require_session, require_write
from app.application.articles import ArticlePage
from app.presentation.http.article_query import parse_query
from app.application.bookmarks import BookmarkOut, list_bookmarks, set_bookmark
from app.presentation.http.dependencies import get_db
from app.core.exceptions import ApiError


class EmptyBody(BaseModel):
    """写路由只接受空 JSON 对象，避免忽略未声明客户端字段。"""

    model_config = ConfigDict(extra="forbid")


bookmarks_router = APIRouter()


@bookmarks_router.get(
    "/api/bookmarks", name="bookmark_list", response_model=ArticlePage,
    dependencies=[Depends(require_session)],
)
def bookmark_list(request: Request, db: DatabaseSession = Depends(get_db)) -> ArticlePage:
    """按服务器收藏时间排序并应用相同筛选，不复制标题快照。"""
    return list_bookmarks(db, parse_query(request.query_params))


def _write(db: DatabaseSession, article_id: int, value: bool, now) -> BookmarkOut:
    """转换已回滚的存储异常为安全 503；业务 404 保持原语义。"""
    try:
        return set_bookmark(db, article_id, value, now)
    except SQLAlchemyError:
        # set_bookmark 已回滚；这里不得返回成功或暴露数据库错误正文。
        raise ApiError("storage_unavailable", "存储暂不可用", 503) from None


@bookmarks_router.put("/api/bookmarks/{article_id}", name="bookmark_put", response_model=BookmarkOut)
def bookmark_put(
    request: Request,
    body: EmptyBody,
    article_id: int = Path(gt=0),
    db: DatabaseSession = Depends(get_db),
    authenticated: AuthenticatedSession = Depends(require_write),
) -> BookmarkOut:
    """提交成功才确认收藏；重复收藏不会重置最初收藏时间。"""
    del body, authenticated
    return _write(db, article_id, True, request.app.state.now())


@bookmarks_router.delete("/api/bookmarks/{article_id}", name="bookmark_delete", response_model=BookmarkOut)
def bookmark_delete(
    request: Request,
    article_id: int = Path(gt=0),
    db: DatabaseSession = Depends(get_db),
    authenticated: AuthenticatedSession = Depends(require_write),
) -> BookmarkOut:
    """取消关系而不删除资讯；没有收藏关系时仍幂等返回 false。"""
    del authenticated
    return _write(db, article_id, False, request.app.state.now())
