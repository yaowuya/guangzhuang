"""原文链接身份、可靠字段合并和收藏引用的持久化行为测试。"""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.articles import Headline, dedup_url, upsert_headline


def test_identity_and_reliable_merge(db, entry_factory, now):
    """只有空格和片段不同的链接更新同一条目，不改变首次来源身份。"""
    entry = entry_factory()
    headline = Headline(entry.source_id, entry.id, " https://example.org/a?x=1#top ", "旧标题")
    first = upsert_headline(db, headline, now)
    second = upsert_headline(db, replace(
        headline, title="新标题", original_url="https://example.org/a?x=1#other"), now)
    db.commit()
    assert first.article_id == second.article_id
    assert first.added is True and second.updated is True
    assert dedup_url("https://x/a?b=1&a=2#x") == "https://x/a?b=1&a=2"
    assert dedup_url("https://x/a?b=1&a=2") != dedup_url("https://x/a?a=2&b=1")


def test_missing_values_do_not_erase_reliable_metadata_or_bookmark(db, entry_factory, now):
    """同链接后续缺值只更新标题，可靠日期、分类、图片与收藏引用保持。"""
    from app.models import Article, Bookmark

    first_entry = entry_factory()
    original = Headline(
        first_entry.source_id, first_entry.id, "https://example.org/a", "旧标题",
        reported_date=date(2025, 12, 31), category_codes=("new_products",),
        region="日本", product_type="护肤", image_url="https://images.example.org/a.jpg",
        image_credit="UNIT_ONLY 摄影",
    )
    first = upsert_headline(db, original, now)
    db.add(Bookmark(article_id=first.article_id, created_at=now))
    db.commit()
    second_entry = entry_factory(source_id=first_entry.source_id)
    changed = upsert_headline(db, Headline(
        second_entry.source_id, second_entry.id, "https://example.org/a#latest", "新标题"),
        now + timedelta(hours=1),
    )
    unchanged = upsert_headline(db, replace(
        original, title="新标题", original_url="https://example.org/a#latest"),
        now + timedelta(hours=2))
    db.commit()
    stored = db.get(Article, first.article_id)
    assert changed == type(changed)(first.article_id, False, True)
    assert unchanged.updated is False
    assert stored.first_entry_id == first_entry.id
    assert stored.reported_date == date(2025, 12, 31)
    assert stored.category_codes == ["new_products"]
    assert (stored.region, stored.product_type) == ("日本", "护肤")
    assert stored.image_url == "https://images.example.org/a.jpg"
    assert stored.updated_at == now + timedelta(hours=1)
    assert db.get(Bookmark, stored.id).article_id == stored.id
    assert "新标题" in stored.search_text
    assert "unit_only 来源" in stored.search_text


def test_image_url_and_credit_update_as_one_consistent_unit(db, entry_factory, now):
    """图片变更但本批无署名时清除旧图署名，不能把旧归属拼到新图。"""
    from app.models import Article

    entry = entry_factory()
    first = Headline(
        entry.source_id, entry.id, "https://example.org/image-item", "标题",
        image_url="https://images.example.org/old.jpg", image_credit="旧图署名",
    )
    result = upsert_headline(db, first, now)
    db.commit()
    changed = upsert_headline(db, replace(
        first, image_url="https://images.example.org/new.jpg", image_credit=None), now)
    db.commit()
    stored = db.get(Article, result.article_id)
    assert changed.updated is True
    assert (stored.image_url, stored.image_credit) == (
        "https://images.example.org/new.jpg", None,
    )


def test_only_first_entry_can_change_article_image_provenance(db, entry_factory, now):
    """同URL的后续入口不能替换首入口图片，许可归属始终可由first_entry_id审计。"""
    from app.models import Article

    first_entry = entry_factory()
    second_entry = entry_factory(source_id=first_entry.source_id)
    first = Headline(
        first_entry.source_id, first_entry.id, "https://example.org/provenance", "标题",
        image_url="https://images.example.org/first.jpg", image_credit="首入口署名",
    )
    result = upsert_headline(db, first, now)
    db.commit()
    upsert_headline(db, Headline(
        second_entry.source_id, second_entry.id, first.original_url, "标题更新",
        image_url="https://images.example.org/second.jpg", image_credit="后续入口署名",
    ), now)
    db.commit()
    stored = db.get(Article, result.article_id)
    assert stored.first_entry_id == first_entry.id
    assert (stored.image_url, stored.image_credit) == (
        "https://images.example.org/first.jpg", "首入口署名",
    )

    empty_result = upsert_headline(db, Headline(
        first_entry.source_id, first_entry.id, "https://example.org/provenance-empty", "无图标题",
    ), now)
    db.commit()
    upsert_headline(db, Headline(
        second_entry.source_id, second_entry.id, "https://example.org/provenance-empty", "后续有图",
        image_url="https://images.example.org/later.jpg", image_credit="后续署名",
    ), now)
    db.commit()
    empty_stored = db.get(Article, empty_result.article_id)
    assert (empty_stored.image_url, empty_stored.image_credit) == (None, None)


def test_different_parameters_case_and_media_remain_independent(db, entry_factory, now):
    """查询参数顺序、大小写及不同媒体链接都保持不同资讯身份。"""
    entry = entry_factory()
    urls = [
        "https://example.org/A?b=1&a=2",
        "https://example.org/a?b=1&a=2",
        "https://example.org/A?a=2&b=1",
        "https://another.example/A?b=1&a=2",
    ]
    ids = [upsert_headline(db, Headline(entry.source_id, entry.id, url, str(index)), now).article_id
           for index, url in enumerate(urls)]
    db.commit()
    assert len(set(ids)) == len(urls)


@pytest.mark.parametrize("changes", [
    {"original_url": "javascript:alert(1)"},
    {"original_url": "https://user:pass@example.org/a"},
    {"original_url": "https://example.org/a#" + "x" * 4097},
    {"original_url": "https://example.org/a\nhttps://evil.example"},
    {"title": " "},
    {"title": "a" * 1001},
    {"image_url": "http://images.example.org/a.jpg"},
    {"region": "r" * 101},
    {"image_credit": "c" * 501},
])
def test_invalid_metadata_is_rejected_before_database_write(db, entry_factory, now, changes):
    """危险链接或超界字段不产生半条资讯，也不触发网络请求。"""
    from sqlalchemy import func, select
    from app.models import Article

    entry = entry_factory()
    headline = Headline(entry.source_id, entry.id, "https://example.org/a", "有效标题")
    with pytest.raises(ValueError):
        upsert_headline(db, replace(headline, **changes), now)
    assert db.scalar(select(func.count()).select_from(Article)) == 0


@pytest.mark.parametrize("codes", [
    ("not_real",), ("trends", "trends"),
    ("regulation_compliance", "trends"),
])
def test_category_codes_are_fixed_unique_and_ordered(db, entry_factory, now, codes):
    """公开写边界拒绝未知、重复或脱离固定七类顺序的分类数组。"""
    from sqlalchemy import func, select
    from app.models import Article

    entry = entry_factory()
    with pytest.raises(ValueError):
        upsert_headline(db, Headline(
            entry.source_id, entry.id, "https://example.org/category", "标题",
            category_codes=codes,
        ), now)
    assert db.scalar(select(func.count()).select_from(Article)) == 0


def test_entry_must_belong_to_the_declared_source(db, entry_factory, now):
    """入口和来源身份不一致时拒绝写入，防止伪造来源署名。"""
    first = entry_factory()
    other = entry_factory(source_id=first.source_id)
    # 显式创建第二站点，使用该站点身份搭配第一站入口。
    from app.models import Source
    source = Source(key="other", name="UNIT_ONLY 第二来源")
    db.add(source)
    db.commit()
    with pytest.raises(ValueError):
        upsert_headline(db, Headline(source.id, other.id, "https://example.org/a", "标题"), now)


def test_same_url_concurrent_sessions_create_one_article(db, entry_factory, now):
    """独立连接并发写相同链接时唯一约束确保只保留一个条目。"""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.models import Article

    entry = entry_factory()
    headline = Headline(entry.source_id, entry.id, "https://example.org/concurrent", "并发标题")
    barrier = Barrier(2)

    def write():
        with Session(db.bind) as contender:
            barrier.wait(timeout=10)
            result = upsert_headline(contender, headline, now)
            contender.commit()
            return result.article_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: write(), range(2)))
    assert ids[0] == ids[1]
    assert db.scalar(select(func.count()).select_from(Article)) == 1
