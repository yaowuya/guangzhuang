"""固定五站六入口注册表；技术候选永不自动等同许可或启用。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import func, select
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


class EntryOut(BaseModel):
    """入口许可与运行状态分开返回，避免网站汇总替代本入口结论。"""

    id: int
    url: str
    kind: str
    verification_status: str
    verification_reason: str | None
    verification_reference: str | None
    enabled: bool
    last_success_at: datetime | None
    last_error: str | None


class SourceOut(BaseModel):
    """固定站点汇总；partial 只用于展示，不能用作执行许可。"""

    id: int
    key: str
    name: str
    language: str | None
    verification_status: str
    reason: str | None
    entries: list[EntryOut]


def _specs(db: Session) -> list[EntrySpec]:
    path = db.info.get("source_config")
    if path is None:
        raise ValueError("数据库会话未绑定固定来源配置")
    return load_registry(path)


def _entry_for_spec(db: Session, spec: EntrySpec) -> tuple[Source, SourceEntry]:
    source = db.scalar(select(Source).where(Source.key == spec.source_key))
    if source is None:
        raise ValueError("固定来源尚未建立")
    entry = db.scalar(select(SourceEntry).where(
        SourceEntry.source_id == source.id, SourceEntry.url == spec.url,
    ))
    if entry is None:
        raise ValueError("固定入口尚未建立")
    return source, entry


def eligible_entries(db: Session) -> list[SourceEntry]:
    """只返回本入口已允许、有依据且启用的记录，并绑定固定运行参数。"""
    specs = {(spec.source_key, spec.url): spec for spec in _specs(db)}
    rows = db.execute(
        select(Source, SourceEntry).join(SourceEntry, SourceEntry.source_id == Source.id).where(
            SourceEntry.enabled.is_(True), SourceEntry.verification_status == "allowed",
            SourceEntry.verification_reason.is_not(None),
            func.length(func.trim(SourceEntry.verification_reason)) > 0,
            SourceEntry.verification_reference.is_not(None),
            func.length(func.trim(SourceEntry.verification_reference)) > 0,
        ).order_by(SourceEntry.id)
    ).all()
    result = []
    for source, entry in rows:
        spec = specs.get((source.key, entry.url))
        if spec is None:
            raise ValueError("已启用入口不在固定配置中")
        result.append(bind_entry_spec(entry, spec))
    return result


def _aggregate(source: Source, entries: list[SourceEntry]) -> None:
    statuses = [entry.verification_status for entry in entries]
    allowed = statuses.count("allowed")
    if statuses and allowed == len(statuses):
        source.verification_status, source.reason = "allowed", "全部固定入口已明确允许"
    elif allowed:
        source.verification_status, source.reason = "partial", f"{allowed}/{len(statuses)} 个入口已明确允许"
    elif "pending" in statuses or not statuses:
        source.verification_status, source.reason = "pending", "仍有入口待核验"
    else:
        source.verification_status, source.reason = "restricted", "全部固定入口受限"


def _safe_probe(probe: dict) -> None:
    allowed = {"attempted", "succeeded", "checked_at", "title_count", "final_url", "error"}
    if not isinstance(probe, dict) or not set(probe) <= allowed:
        raise ValueError("入口运行结果字段无效")
    if not isinstance(probe.get("attempted"), bool) or not isinstance(probe.get("succeeded"), bool):
        raise ValueError("入口运行结果状态无效")
    if type(probe.get("title_count", 0)) is not int or probe.get("title_count", 0) < 0:
        raise ValueError("入口标题计数无效")
    error = probe.get("error")
    if error is not None and (
        not isinstance(error, str) or len(error) > 500
        or any(ord(character) < 32 and character not in "\t" for character in error)
        or any(marker in error.casefold() for marker in ("cookie", "password", "csrf", "token"))
    ):
        raise ValueError("入口运行错误说明无效")


def apply_verification(db: Session, evidence: dict, probe: dict, now: datetime) -> None:
    """先校验使用条件，再用已执行 probe 决定运行启用；网络成功不能反推许可。"""
    allowed_fields = {
        "entry_key", "verification_status", "verification_reason", "verification_reference",
        "automation_allowed", "title_storage_allowed", "image_allowed", "image_hosts",
        "selection", "terms_checked_at",
    }
    if not isinstance(evidence, dict) or not set(evidence) <= allowed_fields:
        raise ValueError("入口核验证据字段无效")
    required = {"entry_key", "verification_status", "verification_reason", "verification_reference",
                "automation_allowed", "title_storage_allowed"}
    if not required <= set(evidence):
        raise ValueError("入口核验证据不完整")
    status = evidence["verification_status"]
    if status not in {"pending", "allowed", "restricted"}:
        raise ValueError("入口核验状态无效")
    reason = evidence["verification_reason"]
    reference = evidence["verification_reference"]
    if reason is not None and (not isinstance(reason, str) or len(reason) > 500):
        raise ValueError("入口核验原因无效")
    if reference is not None and (not isinstance(reference, str) or len(reference) > 4096):
        raise ValueError("入口核验依据无效")
    if status in {"allowed", "restricted"} and (
        not isinstance(reason, str) or not reason.strip()
        or not isinstance(reference, str) or not reference.strip()
    ):
        raise ValueError("明确核验结论必须包含原因和依据")
    if status == "allowed" and not (
        evidence["automation_allowed"] is True and evidence["title_storage_allowed"] is True
    ):
        raise ValueError("允许入口必须明确允许自动读取和标题保存")
    _safe_probe(probe)
    if status != "allowed" and (probe["attempted"] or probe["succeeded"]):
        raise ValueError("未获许可入口不能执行技术探测")
    if probe["succeeded"] and (
        not probe["attempted"] or probe.get("title_count", 0) < 1
        or not isinstance(probe.get("checked_at"), str) or not probe.get("checked_at")
        or not isinstance(probe.get("final_url"), str) or not probe.get("final_url")
    ):
        raise ValueError("成功运行结果缺少可复核信息")
    specs = {spec.key: spec for spec in _specs(db)}
    spec = specs.get(evidence["entry_key"])
    if spec is None:
        raise ValueError("入口不在固定候选中")
    if probe["succeeded"]:
        final = urlsplit(probe["final_url"])
        if final.scheme.lower() != "https" or final.hostname not in spec.allowed_hosts:
            raise ValueError("成功运行结果离开固定入口主机范围")
    source, entry = _entry_for_spec(db, spec)
    entry.verification_status = status
    entry.verification_reason = reason
    entry.verification_reference = reference
    entry.enabled = status == "allowed" and probe["succeeded"] is True
    if probe["succeeded"]:
        entry.last_success_at, entry.last_error = now, None
    elif probe["attempted"]:
        entry.last_error = probe.get("error") or "目标环境未取得有效标题"
    entries = list(db.scalars(select(SourceEntry).where(SourceEntry.source_id == source.id).order_by(SourceEntry.id)))
    _aggregate(source, entries)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def sources_out(db: Session) -> list[SourceOut]:
    """返回固定网站和全部入口的只读状态；许可和最近访问错误分别展示。"""
    result = []
    for source in db.scalars(select(Source).order_by(Source.key)):
        entries = list(db.scalars(select(SourceEntry).where(
            SourceEntry.source_id == source.id).order_by(SourceEntry.id)))
        result.append(SourceOut(
            id=source.id, key=source.key, name=source.name, language=source.language,
            verification_status=source.verification_status, reason=source.reason,
            entries=[EntryOut.model_validate({
                "id": entry.id, "url": entry.url, "kind": entry.kind,
                "verification_status": entry.verification_status,
                "verification_reason": entry.verification_reason,
                "verification_reference": entry.verification_reference,
                "enabled": entry.enabled, "last_success_at": entry.last_success_at,
                "last_error": entry.last_error,
            }) for entry in entries],
        ))
    return result


def _reject_private(value, path: str = "evidence") -> None:
    private = {"body", "content", "html"}
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if (normalized in private or normalized.startswith("raw_")
                    or any(marker in normalized for marker in ("password", "cookie", "csrf", "token"))):
                raise ValueError(f"核验证据包含私密或原始内容字段：{path}.{key}")
            _reject_private(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_private(nested, f"{path}[{index}]")
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError("核验证据包含不可序列化值")


def read_evidence(path: str | Path) -> dict:
    """读取有界安全 JSON 结论；不接受 Cookie、密码或原始网页载荷。"""
    target = Path(path)
    try:
        if target.stat().st_size > 128 * 1024:
            raise ValueError("核验证据文件过大")
        report = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("核验证据不可读取") from error
    if not isinstance(report, dict):
        raise ValueError("核验证据必须为对象")
    _reject_private(report)
    return report


def write_evidence(path: str | Path, report: dict) -> None:
    """原子保存安全 JSON 结论；失败时不覆盖上一份可复核证据。"""
    if not isinstance(report, dict):
        raise ValueError("核验证据必须为对象")
    _reject_private(report)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
