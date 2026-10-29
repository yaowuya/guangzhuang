"""标题资讯的白名单输入、精确链接身份与可靠字段合并。"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
import unicodedata
from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.domain.articles import CategoryCode, Headline, dedup_url, validate_headline
from app.domain.classification import CATEGORY_CODES, CATEGORY_LABELS
from app.infrastructure.persistence.models import Article, Bookmark, Source, SourceEntry


@dataclass(frozen=True)
class WriteResult:
    """表示实际存储变化，不把重复请求次数算作内容更新。"""

    article_id: int
    added: bool
    updated: bool


def _search_text(title: str, source_name: str) -> str:
    return unicodedata.normalize("NFKC", f"{title} {source_name}").casefold()


def upsert_headline(db: Session, headline: Headline, now: datetime) -> WriteResult:
    """按精确链接写入或合并可靠元信息；调用者拥有事务并决定何时提交。"""
    title, key = validate_headline(headline)
    source = db.get(Source, headline.source_id)
    entry = db.get(SourceEntry, headline.first_entry_id)
    if source is None or entry is None or entry.source_id != headline.source_id:
        raise ValueError("来源或入口关系不存在")
    original = headline.original_url.strip()
    values = {
        "source_id": headline.source_id,
        "first_entry_id": headline.first_entry_id,
        "original_url": original,
        "dedup_url": key,
        "title": title,
        "search_text": _search_text(title, source.name),
        "reported_date": headline.reported_date,
        "category_codes": list(headline.category_codes),
        "region": headline.region,
        "product_type": headline.product_type,
        "image_url": headline.image_url,
        "image_credit": headline.image_credit,
        "updated_at": now,
    }
    inserted = db.execute(
        sqlite_insert(Article).values(**values).on_conflict_do_nothing(index_elements=["dedup_url"])
    ).rowcount == 1
    db.flush()
    article = db.scalar(select(Article).where(Article.dedup_url == key))
    if article is None:
        raise RuntimeError("资讯唯一写入后无法读取")
    if inserted:
        return WriteResult(article.id, True, False)

    changes: dict[str, object] = {}
    if article.title != title:
        changes["title"] = title
    if article.original_url != original:
        changes["original_url"] = original
    # 未披露值不能擦除已有可靠元信息；空分类表示未知，不能覆盖已分类结果。
    for field in ("reported_date", "region", "product_type"):
        incoming = getattr(headline, field)
        if incoming is not None and incoming != getattr(article, field):
            changes[field] = incoming
    # 图片 URL 与署名属于同一批证据；换图时旧署名不可继续附着到新图。
    if headline.first_entry_id == article.first_entry_id and headline.image_url is not None:
        if headline.image_url != article.image_url:
            changes["image_url"] = headline.image_url
            if headline.image_credit != article.image_credit:
                changes["image_credit"] = headline.image_credit
        elif headline.image_credit is not None and headline.image_credit != article.image_credit:
            changes["image_credit"] = headline.image_credit
    if headline.category_codes and list(headline.category_codes) != article.category_codes:
        changes["category_codes"] = list(headline.category_codes)
    if changes:
        for field, value in changes.items():
            setattr(article, field, value)
        stored_source = db.get(Source, article.source_id)
        if stored_source is None:
            raise RuntimeError("资讯来源关系已损坏")
        article.search_text = _search_text(title if "title" in changes else article.title, stored_source.name)
        article.updated_at = now
        db.flush()
    return WriteResult(article.id, False, bool(changes))


@dataclass(frozen=True)
class ArticleQuery:
    """一个请求的组合筛选与页码；没有跨请求快照语义。"""

    q: str | None = None
    category: str | None = None
    region: str | None = None
    product_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = 1
    page_size: int = 20


class SourceRef(BaseModel):
    """资讯响应中的稳定来源身份，不携带入口许可或运行详情。"""

    id: int
    key: str
    name: str
    language: str | None


class ArticleOut(BaseModel):
    """浏览器可读取的标题白名单 DTO；不包含正文、摘要或内部去重字段。"""

    id: int
    title: str
    source: SourceRef
    original_url: str
    reported_date: date | None
    category_codes: list[CategoryCode]
    region: str | None
    product_type: str | None
    image_url: str | None
    image_credit: str | None
    updated_at: datetime
    bookmarked: bool


class ArticlePage(BaseModel):
    """服务端页码结果；不承诺跨后台更新的查询快照。"""

    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class FilterOption(BaseModel):
    """筛选值及其显示标签；动态值来自数据库中的明确元信息。"""

    value: str
    label: str


class FiltersOut(BaseModel):
    """固定七类、动态地区/品类及缺值哨兵的筛选契约。"""

    categories: list[FilterOption]
    regions: list[FilterOption]
    product_types: list[FilterOption]
    uncategorized_value: Literal["__uncategorized__"] = "__uncategorized__"
    unknown_value: Literal["__unknown__"] = "__unknown__"


def _validate_dynamic_filters(db: Session, query: ArticleQuery) -> None:
    """动态地区/品类只能消费 filters 已返回值；手改未知深链明确返回 invalid_filter。"""
    for field in ("region", "product_type"):
        value = getattr(query, field)
        if not value or value == "__unknown__":
            continue
        column = getattr(Article, field)
        if not db.scalar(select(exists().where(column == value))):
            raise ApiError("invalid_filter", "筛选条件无效", 400)


def _conditions(query: ArticleQuery):
    conditions = []
    if query.q:
        normalized = unicodedata.normalize("NFKC", query.q).casefold()
        escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(Article.search_text.like(f"%{escaped}%", escape="\\"))
    if query.category == "__uncategorized__":
        conditions.append(func.json_array_length(Article.category_codes) == 0)
    elif query.category:
        values = func.json_each(Article.category_codes).table_valued("value").alias("category_values")
        conditions.append(exists(select(1).select_from(values).where(values.c.value == query.category)))
    for field in ("region", "product_type"):
        value = getattr(query, field)
        column = getattr(Article, field)
        if value == "__unknown__":
            conditions.append(column.is_(None))
        elif value:
            conditions.append(column == value)
    if query.date_from:
        conditions.append(Article.reported_date >= query.date_from)
    if query.date_to:
        conditions.append(Article.reported_date <= query.date_to)
    return conditions


def article_out(db: Session, article: Article, bookmarked: bool | None = None) -> ArticleOut:
    """为列表和详情生成同一 DTO；收藏状态始终由数据库确认。"""
    source = db.get(Source, article.source_id)
    if source is None:
        raise RuntimeError("资讯来源关系已损坏")
    if bookmarked is None:
        bookmarked = db.get(Bookmark, article.id) is not None
    return ArticleOut(
        id=article.id, title=article.title,
        source=SourceRef(id=source.id, key=source.key, name=source.name, language=source.language),
        original_url=article.original_url, reported_date=article.reported_date,
        category_codes=article.category_codes, region=article.region, product_type=article.product_type,
        image_url=article.image_url, image_credit=article.image_credit,
        updated_at=article.updated_at, bookmarked=bookmarked,
    )


def get_article(db: Session, article_id: int) -> ArticleOut:
    """按稳定 ID 读取一条标题 DTO；持久化模型不越过应用层。"""
    article = db.get(Article, article_id)
    if article is None:
        raise ApiError("article_not_found", "资讯不存在", 404)
    return article_out(db, article)


def list_articles(db: Session, query: ArticleQuery, bookmarked_only: bool = False) -> ArticlePage:
    """同一筛选计算总数和当前页；数据变化时页码可位移，不承诺跨请求快照。"""
    _validate_dynamic_filters(db, query)
    marked = exists(select(Bookmark.article_id).where(Bookmark.article_id == Article.id).correlate(Article))
    statement = select(Article, marked.label("bookmarked"))
    if bookmarked_only:
        statement = statement.join(Bookmark, Bookmark.article_id == Article.id)
    conditions = _conditions(query)
    statement = statement.where(*conditions)
    count_source = statement.with_only_columns(Article.id, maintain_column_froms=True).order_by(None).subquery()
    total = db.scalar(select(func.count()).select_from(count_source)) or 0
    if bookmarked_only:
        statement = statement.order_by(Bookmark.created_at.desc(), Article.id.desc())
    else:
        statement = statement.order_by(Article.reported_date.desc().nulls_last(), Article.id.desc())
    statement = statement.limit(query.page_size).offset((query.page - 1) * query.page_size)
    items = [article_out(db, article, bool(bookmarked)) for article, bookmarked in db.execute(statement)]
    return ArticlePage(items=items, total=total, page=query.page, page_size=query.page_size)


def filter_options(db: Session) -> FiltersOut:
    """返回固定七类与数据库已有的非空地区／品类；未知值使用独立哨兵。"""
    def values(column):
        return list(db.scalars(select(column).where(column.is_not(None), func.length(func.trim(column)) > 0)
                               .distinct().order_by(column)))

    return FiltersOut(
        categories=[FilterOption(value=code, label=CATEGORY_LABELS[code]) for code in CATEGORY_CODES],
        regions=[FilterOption(value=value, label=value) for value in values(Article.region)],
        product_types=[FilterOption(value=value, label=value) for value in values(Article.product_type)],
    )
