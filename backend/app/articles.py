"""标题资讯的白名单输入、精确链接身份与可靠字段合并。"""

from dataclasses import dataclass
from datetime import date, datetime
import unicodedata
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import Article, Source, SourceEntry


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
