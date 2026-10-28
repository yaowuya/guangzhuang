"""已认证标题列表、详情与筛选选项；只暴露允许元信息。"""

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session as DatabaseSession

from .api_auth import require_session
from .articles import ArticleOut, ArticlePage, FiltersOut, article_out, filter_options, list_articles, parse_query
from .database import get_db
from .errors import ApiError
from .models import Article


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
    article = db.get(Article, article_id)
    if article is None:
        raise ApiError("article_not_found", "资讯不存在", 404)
    return article_out(db, article)


@articles_router.get("/api/filters", name="filter_options", response_model=FiltersOut)
def filters(db: DatabaseSession = Depends(get_db)) -> FiltersOut:
    """返回固定七类和数据库中已有的明确地区／品类选项。"""
    return filter_options(db)
