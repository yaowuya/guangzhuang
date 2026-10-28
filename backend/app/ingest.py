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
from .models import EntryResult, SourceEntry
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
class _RuntimeEntry:
    """网络阶段只携固定白名单与入口身份，不保持 SQLite 事务或 ORM 懒加载。"""

    id: int
    source_id: int
    url: str
    kind: str
    entry_key: str
    allowed_hosts: tuple[str, ...]
    image_hosts: tuple[str, ...]
    image_allowed: bool
    selection: object | None


@dataclass(frozen=True)
class IngestResult:
    """一次入口事务的实际新增、更新和逐条跳过计数。"""

    added: int
    updated: int
    skipped: dict[str, int]


_SKIP_LABELS = {
    "missing_title": "缺少标题",
    "missing_url": "缺少链接",
    "unsafe_url": "链接不安全",
    "field_too_long": "字段超长",
    "invalid_date": "日期无效但标题已保留",
}


def _skip_summary(skipped: dict[str, int]) -> str | None:
    """把逐条跳过计数压成有界安全文案，区分合法空feed与全无效响应。"""
    items = [(reason, count) for reason, count in skipped.items()
             if reason in _SKIP_LABELS and type(count) is int and count > 0]
    if not items:
        return None
    total = sum(count for _, count in items)
    details = "、".join(f"{_SKIP_LABELS[reason]} {count}" for reason, count in sorted(items))
    return f"跳过 {total} 条：{details}"[:500]


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
        bound = eligible[entry.id]
        runtime = _RuntimeEntry(
            id=bound.id, source_id=bound.source_id, url=bound.url, kind=bound.kind,
            entry_key=bound.entry_key, allowed_hosts=tuple(bound.allowed_hosts),
            image_hosts=tuple(bound.image_hosts), image_allowed=bound.image_allowed,
            selection=bound.selection,
        )
        if result_id is not None:
            candidate_result = db.get(EntryResult, result_id)
            if (candidate_result is None or candidate_result.entry_id != runtime.id
                    or candidate_result.state not in {"pending", "running"}):
                raise ApiError("result_not_found", "入口任务结果不存在", 409)
        rules_path = db.info.get("rules_config")
        if rules_path is None:
            raise ValueError("缺少分类规则配置")
        rules = load_rules(rules_path)
        # 清理许可复核产生的只读事务；网络等待期间不持有 SQLite 事务或 ORM 懒加载。
        db.rollback()
        fetched = client.fetch(runtime.url)
        if runtime.kind == "rss" and fetched.media_type in {
            "application/rss+xml", "application/rdf+xml", "application/xml", "text/xml",
        }:
            batch = parse_rss(fetched.body, runtime)
        elif runtime.kind == "public_list" and fetched.media_type in {"text/html", "application/xhtml+xml"}:
            # SafeClient 已逐跳验证 final_url；相对标题/图片链接必须以最终列表目录为基准。
            batch = parse_list(fetched.body, replace(runtime, url=fetched.final_url))
        else:
            raise ParseError("入口响应类型与固定解析分支不匹配")
        added = updated = 0
        for headline in batch.headlines:
            classification = classify(headline.title, headline.section, rules)
            image_url, image_credit = allowed_image(
                headline.image_url, headline.image_credit, runtime,
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
        stored_entry = db.get(SourceEntry, runtime.id)
        if stored_entry is None:
            raise ApiError("source_not_enabled", "入口未经核验或未启用", 409)
        stored_entry.last_success_at = now
        stored_entry.last_error = None
        if result_id is not None:
            entry_result = db.get(EntryResult, result_id)
            if (entry_result is None or entry_result.entry_id != runtime.id
                    or entry_result.state not in {"pending", "running"}):
                raise ApiError("result_not_found", "入口任务结果不存在", 409)
            entry_result.state = "succeeded"
            entry_result.count_added = added
            entry_result.count_updated = updated
            entry_result.error = _skip_summary(batch.skipped)
            entry_result.finished_at = now
        db.commit()
        return IngestResult(added=added, updated=updated, skipped=dict(batch.skipped))
    except Exception:
        db.rollback()
        raise
