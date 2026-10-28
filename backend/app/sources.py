"""固定五站六入口注册表；技术候选永不自动等同许可或启用。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .models import Source, SourceEntry


CANDIDATES = (
    ("prtimes-rss", "prtimes", "https://prtimes.jp/index.rdf", "rss"),
    ("prtimes-beauty", "prtimes", "https://prtimes.jp/beauty/", "public_list"),
    ("happi-rss", "happi", "https://www.happi.com/feed/", "rss"),
    ("qingyan-list", "qingyan", "https://www.iqingyan.cn/", "public_list"),
    ("pbn-list", "pbn", "https://www.premiumbeautynews.com/en/", "public_list"),
    ("cosin-list", "cosin", "https://cosinkorea.com/", "public_list"),
)
_CANDIDATE_MAP = {candidate[0]: candidate for candidate in CANDIDATES}
_SITE_METADATA = {
    "prtimes": ("PR TIMES", "ja"),
    "happi": ("HAPPI", "en"),
    "qingyan": ("青眼", "zh-CN"),
    "pbn": ("Premium Beauty News", "en"),
    "cosin": ("COSIN Korea", "ko"),
}
_FIELDS = {
    "key", "source_key", "source_name", "language", "url", "kind", "allowed_hosts",
    "image_hosts", "image_allowed", "verification_status", "verification_reason",
    "verification_reference", "enabled", "selection",
}
_SELECTION_FIELDS = {
    "container", "item", "title", "link", "empty", "date", "section", "image", "credit", "date_format",
}


@dataclass(frozen=True)
class EntrySpec:
    """一个固定入口的技术配置；许可结论和实际访问结果由独立证据管理。"""

    key: str
    source_key: str
    source_name: str
    language: str | None
    url: str
    kind: str
    allowed_hosts: tuple[str, ...]
    image_hosts: tuple[str, ...]
    image_allowed: bool
    verification_status: str
    verification_reason: str | None
    verification_reference: str | None
    enabled: bool
    selection: dict[str, str | None] | None


def _validate_identity(spec: EntrySpec) -> None:
    expected = _CANDIDATE_MAP.get(spec.key)
    if expected is None or (spec.key, spec.source_key, spec.url, spec.kind) != expected:
        raise ValueError("来源身份不属于固定候选")
    if (spec.source_name, spec.language) != _SITE_METADATA[spec.source_key]:
        raise ValueError("来源站点名称或语言与固定候选不一致")
    if urlsplit(spec.url).hostname not in spec.allowed_hosts:
        raise ValueError("候选 URL 不在自身固定主机范围")


def load_registry(path: str | Path) -> list[EntrySpec]:
    """读取并验证唯一候选清单；拒绝动态 provider 和配置内伪造许可。"""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("来源配置不可读取") from error
    if not isinstance(raw, list) or len(raw) != len(CANDIDATES):
        raise ValueError("来源清单必须为固定五站六入口")
    specs: list[EntrySpec] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) != _FIELDS:
            raise ValueError("来源配置字段不完整或包含未注册字段")
        expected = CANDIDATES[index]
        identity = (item.get("key"), item.get("source_key"), item.get("url"), item.get("kind"))
        if identity != expected or item.get("kind") not in {"rss", "public_list"}:
            raise ValueError("来源身份不属于固定候选")
        if not isinstance(item.get("source_name"), str) or not item["source_name"].strip():
            raise ValueError("来源名称无效")
        if item.get("language") is not None and not isinstance(item["language"], str):
            raise ValueError("来源语言无效")
        if item.get("verification_status") != "pending" or item.get("enabled") is not False:
            raise ValueError("静态候选不能预先声明获许可或启用")
        if item.get("verification_reason") is not None or item.get("verification_reference") is not None:
            raise ValueError("入口许可必须来自独立核验证据")
        if not isinstance(item.get("allowed_hosts"), list) or not item["allowed_hosts"]:
            raise ValueError("来源主机白名单缺失")
        if any(not isinstance(host, str) or not host for host in item["allowed_hosts"]):
            raise ValueError("来源主机白名单无效")
        if urlsplit(item["url"]).hostname not in item["allowed_hosts"]:
            raise ValueError("候选 URL 不在自身固定主机范围")
        if not isinstance(item.get("image_hosts"), list) or any(
            not isinstance(host, str) or not host for host in item["image_hosts"]
        ):
            raise ValueError("图片主机列表无效")
        if not isinstance(item.get("image_allowed"), bool):
            raise ValueError("图片许可标记无效")
        if item["image_allowed"] and not item["image_hosts"]:
            raise ValueError("允许图片时必须有独立主机范围")
        selection = item.get("selection")
        if selection is not None:
            if not isinstance(selection, dict) or not set(selection) <= _SELECTION_FIELDS:
                raise ValueError("列表选择器字段无效")
            if not {"container", "item", "title", "link"} <= set(selection):
                raise ValueError("列表选择器缺少必要字段")
            if any(value is not None and not isinstance(value, str) for value in selection.values()):
                raise ValueError("列表选择器值无效")
        spec = EntrySpec(
            key=item["key"], source_key=item["source_key"], source_name=item["source_name"],
            language=item["language"], url=item["url"], kind=item["kind"],
            allowed_hosts=tuple(item["allowed_hosts"]), image_hosts=tuple(item["image_hosts"]),
            image_allowed=item["image_allowed"], verification_status="pending",
            verification_reason=None, verification_reference=None, enabled=False,
            selection=selection,
        )
        _validate_identity(spec)
        specs.append(spec)
    return specs


def seed_sources(db: Session, specs: list[EntrySpec]) -> None:
    """只插入缺失的固定身份；重启不得覆盖已核验许可、运行错误或成功时间。"""
    try:
        for spec in specs:
            _validate_identity(spec)
            source = db.scalar(select(Source).where(Source.key == spec.source_key))
            if source is None:
                source = Source(key=spec.source_key, name=spec.source_name, language=spec.language)
                db.add(source)
                db.flush()
            entry = db.scalar(select(SourceEntry).where(
                SourceEntry.source_id == source.id, SourceEntry.url == spec.url,
            ))
            if entry is None:
                db.add(SourceEntry(
                    source_id=source.id, url=spec.url, kind=spec.kind,
                    verification_status="pending", enabled=False,
                ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def bind_entry_spec(entry: SourceEntry, spec: EntrySpec) -> SourceEntry:
    """给当前 ORM 实例绑定受控运行参数；不把临时技术属性写进许可表。"""
    _validate_identity(spec)
    if entry.url != spec.url or entry.kind != spec.kind:
        raise ValueError("数据库入口与固定配置不匹配")
    entry.entry_key = spec.key
    entry.allowed_hosts = spec.allowed_hosts
    entry.image_hosts = spec.image_hosts
    entry.image_allowed = spec.image_allowed
    entry.selection = spec.selection
    return entry
