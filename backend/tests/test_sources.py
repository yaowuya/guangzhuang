"""固定来源候选注册表与默认禁用种子的离线测试。"""

from datetime import UTC, datetime, timedelta
import json

import pytest
from sqlalchemy import select

from app.models import Source, SourceEntry
from app.sources import (
    EntrySpec, apply_verification, bind_entry_spec, eligible_entries, load_registry,
    read_evidence, seed_sources, sources_out, write_evidence,
)


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


def test_entry_evidence_is_not_site_permission(db, settings, now):
    """一个入口允许只让该入口可执行，网站汇总 partial 不放行待核验入口。"""
    specs = load_registry("config/sources.json")
    seed_sources(db, specs)
    db.info["source_config"] = settings.source_config
    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    apply_verification(db, {
        "entry_key": "prtimes-rss", "verification_status": "allowed",
        "verification_reason": "允许自动读取和标题保存", "verification_reference": "unit-reference",
        "automation_allowed": True, "title_storage_allowed": True,
    }, {
        "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
        "title_count": 2, "final_url": "https://prtimes.jp/index.rdf", "error": None,
    }, now)
    eligible = eligible_entries(db)
    assert [entry.entry_key for entry in eligible] == ["prtimes-rss"]
    row = next(source for source in sources_out(db) if source.key == "prtimes")
    assert row.verification_status == "partial"
    assert next(entry for entry in row.entries if entry.url.endswith("/beauty/")).enabled is False
    assert row.reason == "1/2 个入口已明确允许"


def test_allowed_probe_failure_keeps_permission_but_disables_runtime(db, settings, now):
    """运行失败不改写许可结论或已有成功时间，只记录访问错误并禁用。"""
    specs = load_registry("config/sources.json")
    seed_sources(db, specs)
    db.info["source_config"] = settings.source_config
    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    evidence = {
        "entry_key": "happi-rss", "verification_status": "allowed",
        "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
        "automation_allowed": True, "title_storage_allowed": True,
    }
    success = {"attempted": True, "succeeded": True, "checked_at": now.isoformat(),
               "title_count": 1, "final_url": "https://www.happi.com/feed/", "error": None}
    apply_verification(db, evidence, success, now)
    failed = {**success, "succeeded": False, "title_count": 0, "error": "目标环境访问失败"}
    apply_verification(db, evidence, failed, now)
    row = next(source for source in sources_out(db) if source.key == "happi").entries[0]
    assert row.verification_status == "allowed"
    assert row.enabled is False
    assert row.last_success_at == now
    assert row.last_error == "目标环境访问失败"


@pytest.mark.parametrize("evidence,probe", [
    ({"entry_key": "prtimes-rss", "verification_status": "allowed",
      "verification_reason": "", "verification_reference": "ref",
      "automation_allowed": True, "title_storage_allowed": True},
     {"attempted": True, "succeeded": True, "title_count": 1, "error": None}),
    ({"entry_key": "prtimes-rss", "verification_status": "pending",
      "verification_reason": None, "verification_reference": None,
      "automation_allowed": None, "title_storage_allowed": None},
     {"attempted": True, "succeeded": True, "title_count": 1, "error": None}),
])
def test_invalid_permission_evidence_never_enables_entry(db, settings, now, evidence, probe):
    """缺依据或未许可状态不能借一次技术成功获得启用权。"""
    seed_sources(db, load_registry("config/sources.json"))
    db.info["source_config"] = settings.source_config
    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    with pytest.raises(ValueError):
        apply_verification(db, evidence, probe, now)
    assert eligible_entries(db) == []


@pytest.mark.parametrize("probe", [
    {"attempted": True, "succeeded": True, "checked_at": "2026-01-01T00:00:00Z",
     "title_count": 1, "final_url": "https://prtimes.jp/index.rdf", "error": "矛盾错误"},
    {"attempted": False, "succeeded": False, "checked_at": "2026-01-01T00:00:00Z",
     "title_count": 0, "final_url": None, "error": "未探测"},
])
def test_contradictory_probe_states_never_enable_entry(db, settings, now, probe):
    """成功不能携错误，未探测不能伪造检查时间；矛盾证据不得改变入口。"""
    seed_sources(db, load_registry("config/sources.json"))
    db.info["source_config"] = settings.source_config
    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    evidence = {
        "entry_key": "prtimes-rss", "verification_status": "allowed",
        "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
        "automation_allowed": True, "title_storage_allowed": True,
    }
    with pytest.raises(ValueError):
        apply_verification(db, evidence, probe, now)
    assert eligible_entries(db) == []


def test_public_list_cannot_enable_without_frozen_selection(db, settings, now):
    """许可和probe成功也不能启用尚未核验列表结构的public_list入口。"""
    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    db.info["source_config"] = settings.source_config
    seed_sources(db, load_registry(settings.source_config))
    with pytest.raises(ValueError):
        apply_verification(db, {
            "entry_key": "qingyan-list", "verification_status": "allowed",
            "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
            "automation_allowed": True, "title_storage_allowed": True,
            "selection": None,
        }, {
            "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
            "title_count": 1, "final_url": "https://www.iqingyan.cn/", "error": None,
        }, now)
    assert eligible_entries(db) == []


def test_success_probe_must_end_on_the_fixed_entry_host(db, settings, now):
    """即使报告成功，跳到未批准主机也不能启用入口。"""
    seed_sources(db, load_registry("config/sources.json"))
    db.info["source_config"] = settings.source_config
    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    evidence = {
        "entry_key": "prtimes-rss", "verification_status": "allowed",
        "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
        "automation_allowed": True, "title_storage_allowed": True,
    }
    probe = {"attempted": True, "succeeded": True, "checked_at": now.isoformat(),
             "title_count": 1, "final_url": "https://evil.example/feed", "error": None}
    with pytest.raises(ValueError):
        apply_verification(db, evidence, probe, now)
    assert eligible_entries(db) == []


def test_evidence_files_are_atomic_and_reject_private_or_raw_payloads(tmp_path):
    """核验证据只保存结论和引用，不允许 Cookie、密码或原始网页进入文件。"""
    path = tmp_path / "evidence.json"
    report = {"source_key": "unit", "reviewed_at": "2026-01-01T00:00:00Z",
              "environment": "unit", "entries": []}
    write_evidence(path, report)
    assert read_evidence(path) == report
    assert not list(tmp_path.glob("*.tmp"))
    for unsafe in ({**report, "password": "secret"},
                   {**report, "entries": [{"raw_response": "<html>secret</html>"}]},
                   {**report, "entries": [{"raw_html": "secret"}]}):
        with pytest.raises(ValueError):
            write_evidence(path, unsafe)


def test_image_evidence_must_match_config_and_revocation_clears_first_entry_images(
    db, settings, now,
):
    """图片证据与固定配置不一致不得启用；撤销后清除归属该入口的外链和署名。"""
    from app.articles import Headline, upsert_headline
    from app.models import Article

    registry = json.loads(open("config/sources.json", encoding="utf-8").read())
    configured = next(item for item in registry if item["key"] == "prtimes-rss")
    configured["image_allowed"] = True
    configured["image_hosts"] = ["images.example.org"]
    settings.source_config.write_text(json.dumps(registry), encoding="utf-8")
    db.info["source_config"] = settings.source_config
    specs = load_registry(settings.source_config)
    seed_sources(db, specs)
    spec = next(item for item in specs if item.key == "prtimes-rss")
    probe = {"attempted": True, "succeeded": True, "checked_at": now.isoformat(),
             "title_count": 1, "final_url": spec.url, "error": None}
    base = {
        "entry_key": spec.key, "verification_status": "allowed",
        "verification_reason": "UNIT_ONLY 图片许可", "verification_reference": "unit-reference",
        "automation_allowed": True, "title_storage_allowed": True, "selection": None,
    }
    with pytest.raises(ValueError):
        apply_verification(db, {**base, "image_allowed": False, "image_hosts": []}, probe, now)
    with pytest.raises(ValueError):
        apply_verification(db, {**base, "image_allowed": True,
                                "image_hosts": ["other.example"]}, probe, now)
    apply_verification(db, {**base, "image_allowed": True,
                            "image_hosts": ["images.example.org"]}, probe, now)
    entry = eligible_entries(db)[0]
    result = upsert_headline(db, Headline(
        entry.source_id, entry.id, "https://example.org/licensed-image", "标题",
        image_url="https://images.example.org/a.jpg", image_credit="许可署名",
    ), now)
    db.commit()

    configured["image_hosts"] = ["new-images.example.org"]
    settings.source_config.write_text(json.dumps(registry), encoding="utf-8")
    narrowed_spec = next(item for item in load_registry(settings.source_config)
                         if item.key == "prtimes-rss")
    narrowed_at = now + timedelta(minutes=30)
    apply_verification(db, {**base, "image_allowed": True,
                            "image_hosts": ["new-images.example.org"]}, probe, narrowed_at)
    db.expire_all()
    article = db.get(Article, result.article_id)
    assert (article.image_url, article.image_credit, article.updated_at) == (None, None, narrowed_at)

    entry = eligible_entries(db)[0]
    upsert_headline(db, Headline(
        entry.source_id, entry.id, "https://example.org/licensed-image", "标题",
        image_url="https://new-images.example.org/a.jpg", image_credit="新许可署名",
    ), narrowed_at)
    db.commit()
    restricted = {
        "entry_key": narrowed_spec.key, "verification_status": "restricted",
        "verification_reason": "图片与标题使用已撤销", "verification_reference": "unit-revocation",
        "automation_allowed": False, "title_storage_allowed": False,
        "image_allowed": False, "image_hosts": [], "selection": None,
    }
    revoked_at = now + timedelta(hours=1)
    apply_verification(db, restricted, {
        "attempted": False, "succeeded": False, "checked_at": None,
        "title_count": 0, "final_url": None, "error": "许可未明确允许",
    }, revoked_at)
    db.expire_all()
    article = db.get(Article, result.article_id)
    assert (article.image_url, article.image_credit) == (None, None)
    assert article.updated_at == revoked_at


def test_verification_storage_failure_rolls_back_entry_and_image_changes(
    db, settings, now, monkeypatch,
):
    """清图或聚合写入失败必须回滚许可状态，Session保持可继续读取。"""
    from sqlalchemy.exc import OperationalError

    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    db.info["source_config"] = settings.source_config
    seed_sources(db, load_registry(settings.source_config))
    original_execute = db.execute

    def fail_update(statement, *args, **kwargs):
        if statement.__class__.__name__ == "Update":
            raise OperationalError("UNIT verification update", {}, RuntimeError("locked"))
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", fail_update)
    with pytest.raises(OperationalError):
        apply_verification(db, {
            "entry_key": "prtimes-rss", "verification_status": "allowed",
            "verification_reason": "UNIT_ONLY 许可", "verification_reference": "unit-reference",
            "automation_allowed": True, "title_storage_allowed": True,
        }, {
            "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
            "title_count": 1, "final_url": "https://prtimes.jp/index.rdf", "error": None,
        }, now)
    monkeypatch.setattr(db, "execute", original_execute)
    db.expire_all()
    entry = db.scalar(select(SourceEntry).where(SourceEntry.url == "https://prtimes.jp/index.rdf"))
    assert (entry.verification_status, entry.enabled) == ("pending", False)


def test_source_status_api_is_authenticated_and_read_only(user_client, db, settings):
    """已登录浏览器只能读取五站六入口状态，不能通过 API 编辑或启停。"""
    specs = load_registry("config/sources.json")
    seed_sources(db, specs)
    db.info["source_config"] = settings.source_config
    settings.source_config.write_text(open("config/sources.json", encoding="utf-8").read(), encoding="utf-8")
    response = user_client.get("/api/sources")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 5
    assert sum(len(source["entries"]) for source in items) == 6
    assert set(items[0]) == {"id", "key", "name", "language", "verification_status", "reason", "entries"}
    entry = items[0]["entries"][0]
    assert set(entry) == {
        "id", "url", "kind", "verification_status", "verification_reason",
        "verification_reference", "enabled", "last_success_at", "last_error",
    }
    assert user_client.post("/api/sources", json={}).status_code == 405


def test_source_status_api_rejects_anonymous_browser(client):
    """未登录用户不能读取候选站点、许可依据或运行错误。"""
    response = client.get("/api/sources")
    assert (response.status_code, response.json()["code"]) == (401, "unauthenticated")
