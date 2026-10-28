"""标题资讯的白名单输入、精确链接身份与可靠字段合并。"""

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Literal
import unicodedata
from urllib.parse import urlsplit

from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .classification import CATEGORY_CODES, CATEGORY_LABELS
from .errors import ApiError
from .models import Article, Bookmark, Source, SourceEntry


@dataclass(frozen=True)
class Headline:
    """入口解析后的允许元信息；不包含正文、摘要或原始响应。"""

    source_id: int
    first_entry_id: int
    original_url: str
    title: str
    reported_date: date | None = None
    category_codes: tuple[str, ...] = ()
    region: str | None = None
    product_type: str | None = None
    image_url: str | None = None
    image_credit: str | None = None
    section: str | None = None


@dataclass(frozen=True)
class WriteResult:
    """表示实际存储变化，不把重复请求次数算作内容更新。"""

    article_id: int
    added: bool
    updated: bool


def dedup_url(url: str) -> str:
    """仅移除首尾空格和片段；查询参数、顺序、路径和大小写保持原样。"""
    return url.strip().split("#", 1)[0]


def _validate(headline: Headline) -> tuple[str, str]:
    title = headline.title.strip()
    original = headline.original_url.strip()
    key = dedup_url(original)
    parts = urlsplit(key)
    if not title or len(title) > 1000:
        raise ValueError("标题长度无效")
    if (not (1 <= len(original) <= 4096) or not (1 <= len(key) <= 4096)
            or any(ord(character) < 32 or ord(character) == 127 for character in original)
            or parts.scheme.lower() not in {"http", "https"} or not parts.hostname):
        raise ValueError("原文链接无效")
    if parts.username is not None or parts.password is not None:
        raise ValueError("原文链接不能包含凭据")
    if headline.region is not None and len(headline.region) > 100:
        raise ValueError("地区字段过长")
    if headline.product_type is not None and len(headline.product_type) > 100:
        raise ValueError("品类字段过长")
    if headline.image_credit is not None and len(headline.image_credit) > 500:
        raise ValueError("图片署名过长")
    if headline.image_url is not None:
        image = urlsplit(headline.image_url)
        if (len(headline.image_url) > 4096
                or any(ord(character) < 32 or ord(character) == 127 for character in headline.image_url)
                or image.scheme.lower() != "https" or not image.hostname):
            raise ValueError("图片链接无效")
        if image.username is not None or image.password is not None:
            raise ValueError("图片链接不能包含凭据")
    return title, key


def _search_text(title: str, source_name: str) -> str:
    return unicodedata.normalize("NFKC", f"{title} {source_name}").casefold()


def upsert_headline(db: Session, headline: Headline, now: datetime) -> WriteResult:
    """按精确链接写入或合并可靠元信息；调用者拥有事务并决定何时提交。"""
    title, key = _validate(headline)
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
    for field in ("reported_date", "region", "product_type", "image_url", "image_credit"):
        incoming = getattr(headline, field)
        if incoming is not None and incoming != getattr(article, field):
            changes[field] = incoming
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


CategoryCode = Literal[
    "new_products", "trends", "new_ingredients", "research_technology",
    "packaging_formulation", "oem_odm", "regulation_compliance",
]


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
    id: int
    key: str
    name: str
    language: str | None


class ArticleOut(BaseModel):
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
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class FilterOption(BaseModel):
    value: str
    label: str


class FiltersOut(BaseModel):
    categories: list[FilterOption]
    regions: list[FilterOption]
    product_types: list[FilterOption]
    uncategorized_value: Literal["__uncategorized__"] = "__uncategorized__"
    unknown_value: Literal["__unknown__"] = "__unknown__"


def _query_pairs(mapping) -> list[tuple[str, str]]:
    if hasattr(mapping, "multi_items"):
        return list(mapping.multi_items())
    if hasattr(mapping, "items"):
        return [(str(key), str(value)) for key, value in mapping.items()]
    return [(str(key), str(value)) for key, value in mapping]


def _date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError
    return date.fromisoformat(value)


def parse_query(mapping) -> ArticleQuery:
    """严格解析单值查询；重复、未知或超界参数都拒绝，不能静默扩成全库。"""
    allowed = {"q", "category", "region", "product_type", "date_from", "date_to", "page", "page_size"}
    seen: set[str] = set()
    values: dict[str, object] = {}
    try:
        for key, raw in _query_pairs(mapping):
            if key not in allowed or key in seen:
                raise ValueError
            seen.add(key)
            if key in {"page", "page_size"}:
                if not re.fullmatch(r"[1-9]\d*", raw):
                    raise ValueError
                number = int(raw)
                if number > 2_147_483_647 or (key == "page_size" and number > 100):
                    raise ValueError
                values[key] = number
            elif key == "q":
                if len(raw) > 200:
                    raise ValueError
                if raw:
                    values[key] = raw
            elif key == "category":
                if raw != "__uncategorized__" and raw not in CATEGORY_CODES:
                    raise ValueError
                values[key] = raw
            elif key in {"region", "product_type"}:
                if not raw or len(raw) > 100:
                    raise ValueError
                values[key] = raw
            else:
                values[key] = _date(raw)
        query = ArticleQuery(**values)
        if query.date_from and query.date_to and query.date_from > query.date_to:
            raise ValueError
        return query
    except (TypeError, ValueError):
        raise ApiError("invalid_filter", "筛选条件无效", 400) from None


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


def list_articles(db: Session, query: ArticleQuery, bookmarked_only: bool = False) -> ArticlePage:
    """同一筛选计算总数和当前页；数据变化时页码可位移，不承诺跨请求快照。"""
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
