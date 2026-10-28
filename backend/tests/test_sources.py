"""固定来源候选注册表与默认禁用种子的离线测试。"""

from datetime import UTC, datetime
import json

import pytest
from sqlalchemy import select

from app.models import Source, SourceEntry
from app.sources import EntrySpec, bind_entry_spec, load_registry, seed_sources


def test_six_entries_start_disabled(db):
    """五站六入口幂等建立，PR TIMES 两入口共享站点且全部未获许可。"""
    specs = load_registry("config/sources.json")
    seed_sources(db, specs)
    seed_sources(db, specs)
    sources = db.scalars(select(Source).order_by(Source.key)).all()
    entries = db.scalars(select(SourceEntry).order_by(SourceEntry.url)).all()
    assert len(sources) == 5 and len(entries) == 6
    assert all(not entry.enabled and entry.verification_status == "pending" for entry in entries)
    assert len([spec for spec in specs if spec.source_key == "prtimes"]) == 2


def test_reseeding_preserves_entry_permission_and_runtime_state(db):
    """进程重启不能用初始配置覆盖已经核验的入口许可与成功时间。"""
    specs = load_registry("config/sources.json")
    seed_sources(db, specs)
    entry = db.scalar(select(SourceEntry).where(SourceEntry.url == "https://prtimes.jp/index.rdf"))
    entry.verification_status = "allowed"
    entry.verification_reason = "UNIT_ONLY 已核验"
    entry.verification_reference = "unit-reference"
    entry.enabled = True
    entry.last_success_at = datetime(2026, 1, 1, tzinfo=UTC)
    db.commit()
    seed_sources(db, specs)
    db.refresh(entry)
    assert entry.verification_status == "allowed"
    assert entry.enabled is True
    assert entry.last_success_at == datetime(2026, 1, 1, tzinfo=UTC)
    spec = next(spec for spec in specs if spec.key == "prtimes-rss")
    bound = bind_entry_spec(entry, spec)
    assert bound.entry_key == "prtimes-rss"
    assert bound.allowed_hosts == ("prtimes.jp",)
    assert bound.selection is None


def test_registry_rejects_dynamic_or_preapproved_candidates(tmp_path):
    """静态注册表不接受第七入口、任意 provider 或配置内伪造许可。"""
    original = json.loads(open("config/sources.json", encoding="utf-8").read())
    path = tmp_path / "sources.json"
    for mutation in ("extra", "provider", "allowed"):
        data = json.loads(json.dumps(original))
        if mutation == "extra":
            data.append({**data[0], "key": "unknown", "url": "https://outside.example/feed"})
        elif mutation == "provider":
            data[0]["kind"] = "dynamic_plugin"
        else:
            data[0]["enabled"] = True
            data[0]["verification_status"] = "allowed"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError):
            load_registry(path)


def test_registry_requires_consistent_site_metadata_and_fixed_seed_identity(db, tmp_path):
    """同站名称／语言不能冲突，手工构造的第七入口也不能绕过 load_registry。"""
    original = json.loads(open("config/sources.json", encoding="utf-8").read())
    original[1]["source_name"] = "PR TIMES OTHER"
    path = tmp_path / "inconsistent.json"
    path.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(path)

    dynamic = EntrySpec(
        key="outside", source_key="outside", source_name="Outside", language="en",
        url="https://outside.example/feed", kind="rss", allowed_hosts=("outside.example",),
        image_hosts=(), image_allowed=False, verification_status="pending",
        verification_reason=None, verification_reference=None, enabled=False, selection=None,
    )
    with pytest.raises(ValueError):
        seed_sources(db, [dynamic])
    assert db.scalars(select(Source)).all() == []


def test_bind_rejects_mismatched_runtime_spec(db, entry_factory):
    """运行配置不能把一个数据库入口临时绑定成另一站点地址。"""
    entry = entry_factory(url="https://prtimes.jp/index.rdf", kind="rss")
    specs = load_registry("config/sources.json")
    with pytest.raises(ValueError):
        bind_entry_spec(entry, next(spec for spec in specs if spec.key == "happi-rss"))
