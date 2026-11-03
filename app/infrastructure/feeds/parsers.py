"""固定来源的标题元信息解析；不读取、返回或记录文章正文模块。"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
import ipaddress
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as StandardElementTree

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from soupsieve.util import SelectorSyntaxError

from app.domain.articles import Headline

_RSS1 = "http://purl.org/rss/1.0/"
_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_DC = "http://purl.org/dc/elements/1.1/"
_MEDIA = "http://search.yahoo.com/mrss/"


class ParseError(ValueError):
    """来源结构或安全边界无效；消息不包含原始响应。"""


@dataclass(frozen=True)
class ListSelection:
    """逐入口核验后冻结的列表元信息选择器；不含正文或详情页选择器。"""

    container: str
    item: str
    title: str
    link: str
    empty: str | None = None
    date: str | None = None
    section: str | None = None
    image: str | None = None
    credit: str | None = None
    date_format: str | None = None


@dataclass(frozen=True)
class ParseBatch:
    """允许写入的标题元信息和可统计跳过原因；不保存原始响应。"""

    headlines: list[Headline]
    skipped: dict[str, int]


def _parts(tag) -> tuple[str | None, str]:
    if not isinstance(tag, str):
        return None, ""
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return None, tag


def _children(node, local: str, namespaces: set[str | None]):
    result = []
    for child in list(node):
        namespace, name = _parts(child.tag)
        if name == local and namespace in namespaces:
            result.append(child)
    return result


def _text(node, local: str, namespaces: set[str | None]) -> str:
    for child in list(node):
        namespace, name = _parts(child.tag)
        if name == local and namespace in namespaces:
            return "".join(child.itertext()).strip()
    return ""


def _valid_article_url(value: str) -> bool:
    if not value or len(value) > 4096 or "\\" in value:
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username is not None or parsed.password is not None or port is not None and not 1 <= port <= 65535:
        return False
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return True
    return False


def _reported_date(row) -> tuple[date | None, bool]:
    pub_date = _text(row, "pubDate", {None, _RSS1})
    dc_date = _text(row, "date", {_DC})
    raw = pub_date or dc_date
    if not raw:
        return None, False
    try:
        if pub_date:
            return parsedate_to_datetime(raw).date(), False
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            return datetime.fromisoformat(normalized).date(), False
        except ValueError:
            return date.fromisoformat(raw), False
    except (TypeError, ValueError, OverflowError):
        return None, True


def _image_metadata(row) -> tuple[str | None, str | None]:
    image_url = None
    thumbnails = _children(row, "thumbnail", {_MEDIA})
    if thumbnails:
        image_url = (thumbnails[0].get("url") or "").strip() or None
    if image_url is None:
        for enclosure in _children(row, "enclosure", {None, _RSS1}):
            media_type = (enclosure.get("type") or "").lower()
            if media_type.startswith("image/"):
                image_url = (enclosure.get("url") or "").strip() or None
                break
    credit = _text(row, "credit", {_MEDIA}) or None
    return image_url, credit


def parse_rss(raw: bytes, entry) -> ParseBatch:
    """仅读标题、链接、日期、栏目和明确图片元信息；忽略 description/content/summary。"""
    if getattr(entry, "kind", None) != "rss":
        raise ParseError("入口类型不是 RSS")
    if not isinstance(raw, bytes) or len(raw) > 2 * 1024 * 1024:
        raise ParseError("RSS 响应类型或体积无效")
    try:
        root = ElementTree.fromstring(
            raw, forbid_dtd=True, forbid_entities=True, forbid_external=True,
        )
    except (DefusedXmlException, StandardElementTree.ParseError, ValueError, TypeError):
        raise ParseError("RSS XML 不安全或格式无效") from None
    namespace, root_name = _parts(root.tag)
    if root_name == "rss" and namespace is None:
        channels = _children(root, "channel", {None})
        if len(channels) != 1:
            raise ParseError("RSS channel 结构无效")
        rows = _children(channels[0], "item", {None})
        base_namespaces = {None}
    elif root_name == "RDF" and namespace == _RDF:
        rows = _children(root, "item", {_RSS1})
        base_namespaces = {_RSS1}
    else:
        raise ParseError("未识别的 RSS 结构")

    headlines: list[Headline] = []
    skipped: Counter[str] = Counter()
    for row in rows:
        title = _text(row, "title", base_namespaces)
        link = _text(row, "link", base_namespaces)
        if not title:
            skipped["missing_title"] += 1
            continue
        if not link:
            skipped["missing_url"] += 1
            continue
        if len(title) > 1000:
            skipped["field_too_long"] += 1
            continue
        if not _valid_article_url(link):
            skipped["unsafe_url"] += 1
            continue
        reported_date, invalid_date = _reported_date(row)
        if invalid_date:
            skipped["invalid_date"] += 1
        section = _text(row, "category", base_namespaces) or None
        image_url, image_credit = _image_metadata(row)
        headlines.append(Headline(
            source_id=entry.source_id, first_entry_id=entry.id,
            original_url=link, title=title, reported_date=reported_date,
            image_url=image_url, image_credit=image_credit, section=section,
        ))
    return ParseBatch(headlines=headlines, skipped=dict(skipped))


def _list_selection(value) -> ListSelection:
    if isinstance(value, ListSelection):
        selection = value
    elif isinstance(value, dict):
        try:
            selection = ListSelection(**value)
        except TypeError:
            raise ParseError("入口列表选择器无效") from None
    else:
        raise ParseError("入口列表结构尚未核验")
    required = (selection.container, selection.item, selection.title, selection.link)
    optional = (selection.empty, selection.date, selection.section, selection.image, selection.credit)
    if any(not isinstance(selector, str) or not selector.strip() or len(selector) > 500 for selector in required):
        raise ParseError("入口列表选择器无效")
    if any(selector is not None and (
        not isinstance(selector, str) or not selector.strip() or len(selector) > 500
    ) for selector in optional):
        raise ParseError("入口列表选择器无效")
    if selection.date_format is not None and (
        not isinstance(selection.date_format, str) or not selection.date_format
        or len(selection.date_format) > 100
    ):
        raise ParseError("入口日期格式无效")
    return selection


def _selected_text(item, selector: str | None) -> str | None:
    if selector is None:
        return None
    node = item.select_one(selector)
    if node is None:
        return None
    return node.get_text(" ", strip=True) or None


def _list_reported_date(raw: str | None, date_format: str | None) -> tuple[date | None, bool]:
    if raw is None:
        return None, False
    try:
        if date_format:
            return datetime.strptime(raw, date_format).date(), False
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            return datetime.fromisoformat(normalized).date(), False
        except ValueError:
            return date.fromisoformat(raw), False
    except (ValueError, TypeError, OverflowError):
        return None, True


def parse_list(raw: bytes, entry) -> ParseBatch:
    """只消费已核验容器内的固定元信息选择器；从不请求链接页面或执行脚本。"""
    if getattr(entry, "kind", None) != "public_list":
        raise ParseError("入口类型不是公开列表")
    if not isinstance(raw, bytes) or len(raw) > 2 * 1024 * 1024:
        raise ParseError("列表响应类型或体积无效")
    selection = _list_selection(getattr(entry, "selection", None))
    try:
        soup = BeautifulSoup(raw, "html.parser")
        for node in soup.select("script, style, noscript, template"):
            node.decompose()
        containers = soup.select(selection.container)
        if len(containers) != 1:
            raise ParseError("入口列表容器结构已变化")
        container = containers[0]
        items = container.select(selection.item)
        if not items:
            if selection.empty and container.select_one(selection.empty) is not None:
                return ParseBatch(headlines=[], skipped={})
            raise ParseError("入口列表条目结构已变化")
    except SelectorSyntaxError:
        raise ParseError("入口列表选择器无效") from None

    headlines: list[Headline] = []
    skipped: Counter[str] = Counter()
    for item in items:
        try:
            title_node = item.select_one(selection.title)
            link_node = item.select_one(selection.link)
            title = title_node.get_text(" ", strip=True) if title_node is not None else ""
            href = link_node.get("href") if link_node is not None else None
        except SelectorSyntaxError:
            raise ParseError("入口列表选择器无效") from None
        if not title:
            skipped["missing_title"] += 1
            continue
        if not isinstance(href, str) or not href.strip():
            skipped["missing_url"] += 1
            continue
        if len(title) > 1000:
            skipped["field_too_long"] += 1
            continue
        link = urljoin(entry.url, href.strip())
        if not _valid_article_url(link):
            skipped["unsafe_url"] += 1
            continue
        try:
            raw_date = _selected_text(item, selection.date)
            reported_date, invalid_date = _list_reported_date(raw_date, selection.date_format)
            if invalid_date:
                skipped["invalid_date"] += 1
            section = _selected_text(item, selection.section)
            credit = _selected_text(item, selection.credit)
            image_url = None
            if selection.image:
                image_node = item.select_one(selection.image)
                image_src = image_node.get("src") if image_node is not None else None
                if isinstance(image_src, str) and image_src.strip():
                    image_url = urljoin(entry.url, image_src.strip())
        except SelectorSyntaxError:
            raise ParseError("入口列表选择器无效") from None
        headlines.append(Headline(
            source_id=entry.source_id, first_entry_id=entry.id,
            original_url=link, title=title, reported_date=reported_date,
            image_url=image_url, image_credit=credit, section=section,
        ))
    return ParseBatch(headlines=headlines, skipped=dict(skipped))
