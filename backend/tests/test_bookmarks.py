"""持久收藏引用、时间排序与失败回滚的业务服务测试。"""

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.articles import ArticleQuery, Headline, upsert_headline
from app.bookmarks import list_bookmarks, set_bookmark
from app.errors import ApiError
from app.models import Article, Bookmark, SourceEntry


def test_persistent_reference_and_order(db, article_factory, now):
    """收藏按创建时间而非报道日期，重复收藏不重置时间，取消不删资讯。"""
    first = article_factory(reported_date=date(2026, 2, 1))
    second = article_factory(reported_date=date(2026, 1, 1))
    set_bookmark(db, first.id, True, now)
    set_bookmark(db, second.id, True, now + timedelta(seconds=1))
    set_bookmark(db, first.id, True, now + timedelta(seconds=2))
    page = list_bookmarks(db, ArticleQuery())
    assert [item.id for item in page.items] == [second.id, first.id]
    assert all(item.bookmarked for item in page.items)
    assert db.get(Bookmark, first.id).created_at == now
    set_bookmark(db, first.id, False, now)
    assert db.get(type(first), first.id) is not None


def test_same_time_order_persistence_and_same_url_update(db, article_factory, now):
    """同时间按条目 ID 倒序，重开连接和同链接标题更新都维持原收藏引用。"""
    first = article_factory()
    second = article_factory()
    set_bookmark(db, first.id, True, now)
    set_bookmark(db, second.id, True, now)
    entry = db.get(SourceEntry, first.first_entry_id)
    result = upsert_headline(db, Headline(entry.source_id, entry.id, first.original_url, "更新后的标题"), now)
    db.commit()
    assert result.article_id == first.id
    with Session(db.bind) as observer:
        page = list_bookmarks(observer, ArticleQuery())
        assert [item.id for item in page.items] == [max(first.id, second.id), min(first.id, second.id)]
        assert next(item for item in page.items if item.id == first.id).title == "更新后的标题"


def test_missing_article_and_storage_failure_do_not_report_success(db, article_factory, now, monkeypatch):
    """不存在返回业务404，提交失败回滚且不返回 BookmarkOut。"""
    with pytest.raises(ApiError) as missing:
        set_bookmark(db, 999999, True, now)
    assert (missing.value.status, missing.value.code) == (404, "article_not_found")

    article = article_factory()
    original_rollback = db.rollback
    rolled_back = False

    def fail_commit():
        raise OperationalError("unit commit", {}, RuntimeError("UNIT_ONLY"))

    def track_rollback():
        nonlocal rolled_back
        rolled_back = True
        original_rollback()

    monkeypatch.setattr(db, "commit", fail_commit)
    monkeypatch.setattr(db, "rollback", track_rollback)
    with pytest.raises(OperationalError):
        set_bookmark(db, article.id, True, now)
    assert rolled_back is True
    assert db.get(Article, article.id) is not None
    assert db.get(Bookmark, article.id) is None
