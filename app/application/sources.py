"""固定五站六入口注册表；技术候选永不自动等同许可或启用。"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.sources import EntrySpec, validate_entry_identity
from app.infrastructure.configuration import load_registry
from app.infrastructure.persistence.models import Article, Source, SourceEntry


def seed_sources(db: Session, specs: list[EntrySpec]) -> None:
    """只插入缺失的固定身份；重启不得覆盖已核验许可、运行错误或成功时间。"""
    try:
        for spec in specs:
            validate_entry_identity(spec)
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
    validate_entry_identity(spec)
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


def _image_matches_spec(url: str | None, spec: EntrySpec) -> bool:
    """用当前固定配置复核已存图片主机；许可收窄时旧外链必须失效。"""
    if not spec.image_allowed or not url:
        return False
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
    except (ValueError, UnicodeError):
        return False
    return (parsed.scheme.lower() == "https" and parsed.username is None
            and parsed.password is None and host in spec.image_hosts)


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
    attempted = probe["attempted"]
    succeeded = probe["succeeded"]
    checked_at = probe.get("checked_at")
    final_url = probe.get("final_url")
    title_count = probe.get("title_count", 0)
    if succeeded and (
        not attempted or title_count < 1 or not isinstance(checked_at, str) or not checked_at
        or not isinstance(final_url, str) or not final_url or error is not None
    ):
        raise ValueError("成功运行结果字段互相矛盾")
    if attempted and not succeeded and (
        not isinstance(checked_at, str) or not checked_at
        or not isinstance(error, str) or not error
        or final_url is not None and not isinstance(final_url, str)
    ):
        raise ValueError("失败运行结果字段不完整")
    if not attempted and (
        succeeded or title_count != 0 or checked_at is not None or final_url is not None
    ):
        raise ValueError("未探测运行结果不得包含探测数据")


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
    evidence_image = evidence.get("image_allowed", False)
    evidence_hosts = evidence.get("image_hosts", [])
    if type(evidence_image) is not bool or not isinstance(evidence_hosts, list) or any(
        not isinstance(host, str) or not host for host in evidence_hosts
    ):
        raise ValueError("图片许可字段无效")
    if status == "allowed" and (
        evidence_image is not spec.image_allowed
        or tuple(evidence_hosts) != spec.image_hosts
        or evidence.get("selection") != spec.selection
    ):
        raise ValueError("核验证据与固定入口图片/列表配置不一致")
    if status == "allowed" and spec.kind == "public_list" and spec.selection is None:
        raise ValueError("公开列表获准前必须冻结已验证选择器")
    if spec.kind == "rss" and spec.selection is not None:
        raise ValueError("RSS入口不能携带公开列表选择器")
    terms_checked_at = evidence.get("terms_checked_at")
    if terms_checked_at is not None and (
        not isinstance(terms_checked_at, str) or not terms_checked_at.strip()
    ):
        raise ValueError("条款核验时间无效")
    if probe["succeeded"]:
        final = urlsplit(probe["final_url"])
        if final.scheme.lower() != "https" or final.hostname not in spec.allowed_hosts:
            raise ValueError("成功运行结果离开固定入口主机范围")
    try:
        source, entry = _entry_for_spec(db, spec)
        entry.verification_status = status
        entry.verification_reason = reason
        entry.verification_reference = reference
        entry.enabled = status == "allowed" and probe["succeeded"] is True
        image_permitted = status == "allowed" and evidence_image and spec.image_allowed
        if not image_permitted:
            # Article.first_entry_id 是图片许可的稳定归属；撤销或配置不匹配时同步清除外链与署名。
            db.execute(update(Article).where(
                Article.first_entry_id == entry.id,
                Article.image_url.is_not(None) | Article.image_credit.is_not(None),
            ).values(image_url=None, image_credit=None, updated_at=now))
        else:
            for article in db.scalars(select(Article).where(
                Article.first_entry_id == entry.id, Article.image_url.is_not(None),
            )):
                if not _image_matches_spec(article.image_url, spec):
                    article.image_url = None
                    article.image_credit = None
                    article.updated_at = now
        if probe["succeeded"]:
            entry.last_success_at, entry.last_error = now, None
        elif probe["attempted"]:
            entry.last_error = probe.get("error") or "目标环境未取得有效标题"
        entries = list(db.scalars(select(SourceEntry).where(
            SourceEntry.source_id == source.id).order_by(SourceEntry.id)))
        _aggregate(source, entries)
        db.commit()
    except Exception:
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
