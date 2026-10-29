"""标题值对象、链接身份和写入前白名单校验。"""

from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from app.domain.classification import CATEGORY_CODES

CategoryCode = Literal[
    "new_products", "trends", "new_ingredients", "research_technology",
    "packaging_formulation", "oem_odm", "regulation_compliance",
]


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


def dedup_url(url: str) -> str:
    """仅移除首尾空格和片段；查询参数、顺序、路径和大小写保持原样。"""
    return url.strip().split("#", 1)[0]


def validate_headline(headline: Headline) -> tuple[str, str]:
    """规范标题并验证业务白名单，返回标题与精确链接身份。"""
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
    codes = tuple(headline.category_codes)
    if (len(set(codes)) != len(codes) or any(code not in CATEGORY_CODES for code in codes)
            or codes != tuple(code for code in CATEGORY_CODES if code in codes)):
        raise ValueError("分类代码无效、重复或顺序错误")
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
