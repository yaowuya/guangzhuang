"""单人收藏关系的幂等写入与服务器排序读取。"""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .articles import ArticlePage, ArticleQuery, list_articles
from .errors import ApiError
from .models import Article, Bookmark


class BookmarkOut(BaseModel):
    """收藏写入的服务端确认；前端只能据此更新已显示状态。"""

    article_id: int
    bookmarked: bool


def set_bookmark(db: Session, article_id: int, value: bool, now: datetime) -> BookmarkOut:
    """幂等改变引用；重复收藏不重置最初时间，取消不删除资讯。"""
    if db.get(Article, article_id) is None:
        raise ApiError("article_not_found", "资讯不存在", 404)
    try:
        if value:
            db.execute(
                sqlite_insert(Bookmark).values(article_id=article_id, created_at=now)
                .on_conflict_do_nothing(index_elements=["article_id"])
            )
        else:
            db.execute(delete(Bookmark).where(Bookmark.article_id == article_id))
        db.commit()
    except SQLAlchemyError:
        # 写失败必须恢复 Session 可用状态，调用 API 再转换为安全 503。
        db.rollback()
        raise
    return BookmarkOut(article_id=article_id, bookmarked=value)


def list_bookmarks(db: Session, query: ArticleQuery) -> ArticlePage:
    """复用标题查询条件，但排序和 membership 始终由收藏关系在服务器决定。"""
    return list_articles(db, query, bookmarked_only=True)
