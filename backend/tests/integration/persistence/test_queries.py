"""标题组合筛选、服务器排序与收藏状态的查询行为测试。"""

from datetime import date

import pytest

from app.application.articles import ArticleQuery, filter_options, list_articles
from app.presentation.http.article_query import parse_query
from app.core.exceptions import ApiError
from app.infrastructure.persistence.models import Bookmark


def test_filters_order_and_page_movement(db, article_factory, now):
    """首页已知报道日期倒序、未知日期最后；跨更新页码允许位移。"""
    unknown = article_factory(reported_date=None)
    article_factory(reported_date=date(2026, 1, 1))
    latest = article_factory(reported_date=date(2026, 2, 1))
    first = list_articles(db, ArticleQuery(page=1, page_size=1))
    assert [item.id for item in first.items] == [latest.id]
    article_factory(reported_date=date(2026, 3, 1))
    second = list_articles(db, ArticleQuery(page=2, page_size=1))
    assert second.items[0].id == latest.id  # 明确接受后台插入后的跨页位移。
    assert list_articles(db, ArticleQuery()).items[-1].id == unknown.id


def test_combined_filters_search_literals_unknowns_and_bookmarks(db, article_factory, now):
    """所有条件取交集，LIKE 通配符保持字面，缺值哨兵只匹配真正 NULL／空数组。"""
    target = article_factory(
        title="100%_ 精华新品", search_text="100%_ 精华新品 unit_only 来源",
        reported_date=date(2026, 2, 1), category_codes=["new_products", "new_ingredients"],
        region=None, product_type="护肤",
    )
    article_factory(title="其它", search_text="其它 unit_only 来源",
                    reported_date=date(2026, 2, 1), category_codes=["new_products"],
                    region="日本", product_type="护肤")
    db.add(Bookmark(article_id=target.id, created_at=now))
    db.commit()
    query = ArticleQuery(q="100%_", category="new_ingredients", region="__unknown__",
                         product_type="护肤", date_from=date(2026, 1, 1),
                         date_to=date(2026, 2, 1))
    result = list_articles(db, query)
    assert [item.id for item in result.items] == [target.id]
    assert result.items[0].bookmarked is True
    assert list_articles(db, query, bookmarked_only=True).items[0].id == target.id


def test_server_total_page_and_stable_ties(db, article_factory):
    """数据不变时同日期按 ID 倒序；总数独立于页容量，超页返回空而非重排。"""
    day = date(2026, 1, 1)
    ids = [article_factory(reported_date=day).id for _ in range(3)]
    page = list_articles(db, ArticleQuery(page=1, page_size=2))
    assert (page.total, page.page, page.page_size) == (3, 1, 2)
    assert [item.id for item in page.items] == sorted(ids, reverse=True)[:2]
    assert [item.id for item in list_articles(db, ArticleQuery(page=2, page_size=2)).items] == [min(ids)]
    assert list_articles(db, ArticleQuery(page=3, page_size=2)).items == []


def test_bookmark_list_is_server_sorted_by_collection_time(db, article_factory, now):
    """收藏列表按收藏时间再条目 ID，和首页报道日期顺序明确分开。"""
    from datetime import timedelta

    older_report = article_factory(reported_date=date(2020, 1, 1))
    newer_report = article_factory(reported_date=date(2026, 1, 1))
    db.add_all([
        Bookmark(article_id=newer_report.id, created_at=now),
        Bookmark(article_id=older_report.id, created_at=now + timedelta(minutes=1)),
    ])
    db.commit()
    assert [item.id for item in list_articles(db, ArticleQuery(), bookmarked_only=True).items] == [
        older_report.id, newer_report.id,
    ]
    assert all(item.bookmarked for item in list_articles(db, ArticleQuery(), bookmarked_only=True).items)


def test_unknown_dynamic_filter_values_are_rejected_not_silently_empty(db, article_factory):
    """手改URL的未知地区/品类由服务器400解释，真实已返回选项仍可产生空交集。"""
    article_factory(region="日本", product_type="护肤")
    for query in (ArticleQuery(region="火星"), ArticleQuery(product_type="未知品类")):
        with pytest.raises(ApiError) as error:
            list_articles(db, query)
        assert (error.value.status, error.value.code) == (400, "invalid_filter")
    assert list_articles(db, ArticleQuery(region="__unknown__")).total == 0


def test_filter_options_are_fixed_categories_and_actual_nonempty_values(db, article_factory):
    """七类次序固定，地区／品类只来自已有明确值，未知值另有哨兵。"""
    article_factory(region="日本", product_type="护肤", category_codes=[])
    article_factory(region=None, product_type=None, category_codes=["trends"])
    options = filter_options(db)
    assert [item.value for item in options.categories] == [
        "new_products", "trends", "new_ingredients", "research_technology",
        "packaging_formulation", "oem_odm", "regulation_compliance",
    ]
    assert [item.value for item in options.regions] == ["日本"]
    assert [item.value for item in options.product_types] == ["护肤"]
    assert (options.uncategorized_value, options.unknown_value) == ("__uncategorized__", "__unknown__")


def test_source_name_search_is_normalized_and_percent_underscore_are_literal(db, article_factory):
    """搜索只用已存标题与来源文本；SQL 通配符按普通字符匹配。"""
    target = article_factory(title="ＡＢＣ 100%_", search_text="abc 100%_ unit_only 来源")
    article_factory(title="相似但不匹配", search_text="abc 100xx unit_only 来源")
    assert [item.id for item in list_articles(db, ArticleQuery(q="ABC 100%_")).items] == [target.id]
    assert list_articles(db, ArticleQuery(q="不存在")).total == 0


@pytest.mark.parametrize("query", [
    [("page", "1"), ("page", "2")], [("page", "0")], [("page_size", "101")],
    [("category", "unknown")], [("date_from", "2026-02-30")], [("page", "999999999999999999999999")],
    [("date_from", "2026-02-02"), ("date_to", "2026-02-01")], [("extra", "x")],
])
def test_parse_query_rejects_duplicate_and_invalid_values(query):
    """不把非法条件静默放宽为全库查询。"""
    with pytest.raises(ApiError) as error:
        parse_query(query)
    assert (error.value.status, error.value.code) == (400, "invalid_filter")
