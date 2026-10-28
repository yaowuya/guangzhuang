"""获许可入口的图片边界与单入口标题采集事务。"""

from dataclasses import dataclass, replace
from datetime import datetime
import ipaddress
from urllib.parse import urlsplit

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .articles import upsert_headline
from .classification import classify, load_rules
from .errors import ApiError
from .models import EntryResult
from .parsers import ParseError, parse_list, parse_rss
from .safe_http import FetchError
from .sources import eligible_entries


def _image_host(value: str) -> str | None:
    try:
        normalized = value.encode("idna").decode("ascii").lower()
    except (AttributeError, UnicodeError):
        return None
    labels = normalized.split(".")
    if len(labels) < 2 or normalized.endswith(".") or any(
        not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
        or any(not (character.isascii() and (character.isalnum() or character == "-")) for character in label)
        for label in labels
    ):
        return None
    return normalized


def allowed_image(url: str | None, credit: str | None, entry) -> tuple[str | None, str | None]:
    """只返回浏览器可直连的获许可外链；不下载、探测、代理、转存或内嵌图片。"""
    if getattr(entry, "image_allowed", False) is not True or not isinstance(url, str):
        return None, None
    candidate = url.strip()
    if not candidate or len(candidate) > 4096 or "\\" in candidate:
        return None, None
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        return None, None
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        return None, None
    if parsed.scheme.lower() != "https" or port not in (None, 443):
        return None, None
    if parsed.username is not None or parsed.password is not None or not parsed.hostname:
        return None, None
    host = _image_host(parsed.hostname)
    if host is None:
        return None, None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None, None
    allowed = {_image_host(value) for value in getattr(entry, "image_hosts", ())}
    if None in allowed or host not in allowed:
        return None, None
    safe_credit = None
    if isinstance(credit, str):
        stripped = credit.strip()
        if (stripped and len(stripped) <= 500
                and not any(ord(character) < 32 or ord(character) == 127 for character in stripped)):
            safe_credit = stripped
    return candidate, safe_credit


@dataclass(frozen=True)
class IngestResult:
    """一次入口事务的实际新增、更新和逐条跳过计数。"""

    added: int
    updated: int
    skipped: dict[str, int]


def safe_error(error: Exception) -> str:
    """把内部失败缩减为可展示短说明；不包含原始响应、SQL、URL凭据或异常栈。"""
    if isinstance(error, ApiError):
        message = error.message
    elif isinstance(error, FetchError):
        message = error.message
    elif isinstance(error, ParseError):
        message = "来源元信息解析失败"
    elif isinstance(error, SQLAlchemyError):
        message = "存储暂不可用"
    elif isinstance(error, ValueError):
        message = "入口数据无效"
    else:
        message = "入口处理失败"
    return message[:500]


def ingest_entry(
    db: Session,
    entry,
    client,
    now: datetime,
    result_id: int | None = None,
) -> IngestResult:
    """一次受控fetch后原子解析、分类、写入；失败回滚且不污染最后成功状态。"""
    try:
        if db.new or db.dirty or db.deleted:
            raise ValueError("采集必须使用无待提交写入的会话")
        eligible = {candidate.id: candidate for candidate in eligible_entries(db)}
        if entry.id not in eligible:
            raise ApiError("source_not_enabled", "入口未经核验或未启用", 409)
        # eligible_entries 给同一 ORM 身份绑定固定运行参数；网络阶段尚未取得写锁。
        entry = eligible[entry.id]
        entry_result = None
        if result_id is not None:
            entry_result = db.get(EntryResult, result_id)
            if (entry_result is None or entry_result.entry_id != entry.id
                    or entry_result.state not in {"pending", "running"}):
                raise ApiError("result_not_found", "入口任务结果不存在", 409)
        rules_path = db.info.get("rules_config")
        if rules_path is None:
            raise ValueError("缺少分类规则配置")
        rules = load_rules(rules_path)
        fetched = client.fetch(entry.url)
        if entry.kind == "rss" and fetched.media_type in {
            "application/rss+xml", "application/rdf+xml", "application/xml", "text/xml",
        }:
            batch = parse_rss(fetched.body, entry)
        elif entry.kind == "public_list" and fetched.media_type in {"text/html", "application/xhtml+xml"}:
            batch = parse_list(fetched.body, entry)
        else:
            raise ParseError("入口响应类型与固定解析分支不匹配")
        added = updated = 0
        for headline in batch.headlines:
            classification = classify(headline.title, headline.section, rules)
            image_url, image_credit = allowed_image(
                headline.image_url, headline.image_credit, entry,
            )
            result = upsert_headline(db, replace(
                headline,
                category_codes=classification.category_codes,
                region=classification.region,
                product_type=classification.product_type,
                image_url=image_url,
                image_credit=image_credit,
            ), now)
            added += int(result.added)
            updated += int(result.updated)
        entry.last_success_at = now
        entry.last_error = None
        if entry_result is not None:
            entry_result.state = "succeeded"
            entry_result.count_added = added
            entry_result.count_updated = updated
            entry_result.error = None
            entry_result.finished_at = now
        db.commit()
        return IngestResult(added=added, updated=updated, skipped=dict(batch.skipped))
    except Exception:
        db.rollback()
        raise
