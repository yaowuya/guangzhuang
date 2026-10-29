"""已认证标题列表、详情与筛选选项；只暴露允许元信息。"""

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session as DatabaseSession

from app.presentation.http.auth import require_session
from app.application.articles import ArticleOut, ArticlePage, FiltersOut, filter_options, get_article, list_articles
from app.presentation.http.article_query import parse_query
from app.presentation.http.dependencies import get_db


articles_router = APIRouter(dependencies=[Depends(require_session)])


@articles_router.get("/api/articles", name="article_list", response_model=ArticlePage)
def article_list(request: Request, db: DatabaseSession = Depends(get_db)) -> ArticlePage:
    """返回服务端组合筛选和页码结果，不复制正文或客户端排序。"""
    return list_articles(db, parse_query(request.query_params))


@articles_router.get("/api/articles/{article_id}", name="article_detail", response_model=ArticleOut)
def article_detail(
    article_id: int = Path(gt=0),
    db: DatabaseSession = Depends(get_db),
) -> ArticleOut:
    """读取同一条目身份和当前收藏标记，不根据缺值推断产品信息。"""
    return get_article(db, article_id)


@articles_router.get("/api/filters", name="filter_options", response_model=FiltersOut)
def filters(db: DatabaseSession = Depends(get_db)) -> FiltersOut:
    """返回固定七类和数据库中已有的明确地区／品类选项。"""
    return filter_options(db)
