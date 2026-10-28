"""图片外链边界与单入口采集事务测试。"""

from pathlib import Path
import socket

import pytest
from sqlalchemy import select

from app.errors import ApiError
from app.ingest import allowed_image, ingest_entry, safe_error
from app.models import Article, EntryResult
from app.parsers import ParseError
from app.safe_http import FetchError, Limits, SafeClient
from app.sources import apply_verification, eligible_entries, load_registry, seed_sources


def approved_entry(db, settings, now, key="prtimes-rss"):
    """用固定本地注册表和合成核验结果建立测试入口；不访问真实站点。"""
    settings.source_config.write_text(Path("config/sources.json").read_text(encoding="utf-8"), encoding="utf-8")
    settings.rules_config.write_text(Path("config/classification.json").read_text(encoding="utf-8"), encoding="utf-8")
    db.info.update(source_config=settings.source_config, rules_config=settings.rules_config)
    seed_sources(db, load_registry(settings.source_config))
    spec = next(spec for spec in load_registry(settings.source_config) if spec.key == key)
    apply_verification(db, {
        "entry_key": key, "verification_status": "allowed",
        "verification_reason": "UNIT_ONLY 允许标题测试", "verification_reference": "unit-reference",
        "automation_allowed": True, "title_storage_allowed": True,
    }, {
        "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
        "title_count": 1, "final_url": spec.url, "error": None,
    }, now)
    return next(entry for entry in eligible_entries(db) if entry.entry_key == key)


def test_entry_atomicity_zero_and_invalid_rows(db, settings, http_lab, now):
    """合法零新增仍是成功；缺关键字段只计跳过并原子更新入口成功时间。"""
    entry = approved_entry(db, settings, now)
    entry.last_success_at = None
    db.commit()
    http_lab.reply(entry.url, body=b"<rss><channel><item><title>No link</title></item></channel></rss>")
    result = ingest_entry(db, entry, http_lab.client_for(entry), now)
    assert result.added == result.updated == 0
    assert result.skipped["missing_url"] == 1
    assert db.scalars(select(Article)).all() == []
    assert entry.last_success_at == now
    assert len(http_lab.connections) == 1


def test_ingest_classifies_upserts_and_keeps_unknown_fields(db, settings, http_lab, now):
    """标题分类和同链接更新计实际变化，后续缺值不擦除明示日期。"""
    entry = approved_entry(db, settings, now)
    entry.last_success_at = None
    db.commit()
    first = b"""<rss><channel><item><title>New ingredient serum launched in Japan</title>
      <link>https://example.org/a#first</link><pubDate>Thu, 01 Jan 2026 00:00:00 +0000</pubDate>
      <category>New products</category><enclosure url='https://images.example.org/a.jpg' type='image/jpeg'/>
      </item></channel></rss>"""
    http_lab.reply(entry.url, body=first)
    created = ingest_entry(db, entry, http_lab.client_for(entry), now)
    assert (created.added, created.updated) == (1, 0)
    article = db.scalar(select(Article))
    assert article.reported_date.isoformat() == "2026-01-01"
    assert article.category_codes == ["new_products", "new_ingredients"]
    assert (article.region, article.product_type) == ("日本", "护肤")
    assert article.image_url is None  # 图片许可与标题许可独立。

    http_lab.reply(entry.url, body=b"""<rss><channel><item><title>Updated title</title>
      <link>https://example.org/a#second</link></item></channel></rss>""")
    changed = ingest_entry(db, entry, http_lab.client_for(entry), now)
    db.refresh(article)
    assert (changed.added, changed.updated, article.title) == (0, 1, "Updated title")
    assert article.reported_date.isoformat() == "2026-01-01"
    assert article.category_codes == ["new_products", "new_ingredients"]


def test_ingest_updates_entry_result_in_same_transaction(db, settings, http_lab, job_factory, now):
    """成功条目和任务结果计数同一次提交，零错误文本和结束时间一起落库。"""
    entry = approved_entry(db, settings, now)
    job = job_factory(entry_ids=[entry.id])
    result_row = job.entries[0]
    http_lab.reply(entry.url, body=b"""<rss><channel><item><title>New product</title>
      <link>https://example.org/result</link></item></channel></rss>""")
    outcome = ingest_entry(db, entry, http_lab.client_for(entry), now, result_id=result_row.id)
    db.refresh(result_row)
    assert outcome.added == 1
    assert (result_row.state, result_row.count_added, result_row.count_updated) == ("succeeded", 1, 0)
    assert result_row.finished_at == now and result_row.error is None


def test_ingest_failure_rolls_back_partial_articles_and_success_metadata(
    db, settings, http_lab, now, monkeypatch,
):
    """第二条写入失败时第一条也回滚，成功时间不前移，错误文本不保存原始哨兵。"""
    from app import ingest as ingest_module

    entry = approved_entry(db, settings, now)
    entry.last_success_at = None
    db.commit()
    http_lab.reply(entry.url, body=b"""<rss><channel>
      <item><title>First</title><link>https://example.org/first</link></item>
      <item><title>Second</title><link>https://example.org/second</link></item>
      </channel></rss>""")
    original = ingest_module.upsert_headline
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("RAW_BODY_SENTINEL")
        return original(*args, **kwargs)

    monkeypatch.setattr(ingest_module, "upsert_headline", fail_second)
    with pytest.raises(RuntimeError):
        ingest_entry(db, entry, http_lab.client_for(entry), now)
    assert db.scalars(select(Article)).all() == []
    db.refresh(entry)
    assert entry.last_success_at is None
    assert "SENTINEL" not in safe_error(RuntimeError("RAW_BODY_SENTINEL"))


def test_dirty_session_and_media_mismatch_fail_before_success(db, settings, http_lab, now):
    """待提交写入不会跨网络等待；RSS返回HTML类型也不能按成功处理。"""
    entry = approved_entry(db, settings, now)
    entry.last_error = "uncommitted"
    with pytest.raises(ValueError):
        ingest_entry(db, entry, http_lab.client_for(entry), now)
    assert http_lab.connections == []
    db.refresh(entry)
    old_success = entry.last_success_at
    http_lab.reply(entry.url, headers={"Content-Type": "text/html"},
                   body=b"<rss><channel></channel></rss>")
    with pytest.raises(ParseError):
        ingest_entry(db, entry, http_lab.client_for(entry), now)
    db.refresh(entry)
    assert entry.last_success_at == old_success


def test_disabled_entry_fails_before_fetch(db, settings, http_lab, now):
    """入口一旦禁用即使调用方提供client也不能发送请求。"""
    entry = approved_entry(db, settings, now)
    entry.enabled = False
    db.commit()
    with pytest.raises(ApiError) as error:
        ingest_entry(db, entry, http_lab.client_for(entry), now)
    assert (error.value.status, error.value.code) == (409, "source_not_enabled")
    assert http_lab.connections == []


def test_public_list_branch_uses_only_frozen_selection(db, settings, http_lab, now):
    """公开列表分支消费配置中的核验选择器，同样只写标题元信息。"""
    import json

    registry = json.loads(Path("config/sources.json").read_text(encoding="utf-8"))
    selected = next(item for item in registry if item["key"] == "qingyan-list")
    selected["selection"] = {
        "container": "main.feed", "item": "article.card", "title": "h2", "link": "a.read",
    }
    settings.source_config.write_text(json.dumps(registry), encoding="utf-8")
    settings.rules_config.write_text(Path("config/classification.json").read_text(encoding="utf-8"), encoding="utf-8")
    db.info.update(source_config=settings.source_config, rules_config=settings.rules_config)
    specs = load_registry(settings.source_config)
    seed_sources(db, specs)
    spec = next(spec for spec in specs if spec.key == "qingyan-list")
    apply_verification(db, {
        "entry_key": spec.key, "verification_status": "allowed",
        "verification_reason": "UNIT_ONLY 允许标题测试", "verification_reference": "unit-reference",
        "automation_allowed": True, "title_storage_allowed": True,
    }, {
        "attempted": True, "succeeded": True, "checked_at": now.isoformat(),
        "title_count": 1, "final_url": spec.url, "error": None,
    }, now)
    entry = next(item for item in eligible_entries(db) if item.entry_key == spec.key)
    http_lab.reply(entry.url, headers={"Content-Type": "text/html"}, body=b"""
      <main class='feed'><article class='card'><h2>New product</h2>
      <a class='read' href='/article/1'>Read</a><div class='body'>RAW_SENTINEL</div>
      </article></main>""")
    result = ingest_entry(db, entry, http_lab.client_for(entry), now)
    assert result.added == 1
    article = db.scalar(select(Article))
    assert (article.title, article.category_codes) == ("New product", ["new_products"])
    assert not hasattr(article, "body")


def test_fetch_parse_and_result_link_failures_leave_no_success(db, settings, http_lab, now):
    """过大/畸形响应和错误result_id均回滚标题及成功时间。"""
    entry = approved_entry(db, settings, now)
    entry.last_success_at = None
    db.commit()
    http_lab.reply(entry.url, body=b"<rss><channel><item></rss>")
    with pytest.raises(ParseError):
        ingest_entry(db, entry, http_lab.client_for(entry), now)
    db.refresh(entry)
    assert entry.last_success_at is None

    http_lab.reply(entry.url, body=b"x" * 17)
    tiny_client = SafeClient(entry.allowed_hosts, http_lab.resolve, http_lab.dial, Limits(max_bytes=16))
    with pytest.raises(FetchError):
        ingest_entry(db, entry, tiny_client, now)
    db.refresh(entry)
    assert entry.last_success_at is None

    http_lab.reply(entry.url, body=b"""<rss><channel><item><title>Valid</title>
      <link>https://example.org/rollback-result</link></item></channel></rss>""")
    with pytest.raises(ApiError):
        ingest_entry(db, entry, http_lab.client_for(entry), now, result_id=999999)
    assert db.scalars(select(Article)).all() == []
    db.refresh(entry)
    assert entry.last_success_at is None


def test_safe_error_never_echoes_parser_or_unknown_payloads():
    """可展示错误只使用受控消息，不复制原始响应或未知异常正文。"""
    assert safe_error(ParseError("RAW_BODY_SENTINEL")) == "来源元信息解析失败"
    assert "SENTINEL" not in safe_error(ValueError("RAW_BODY_SENTINEL"))
    assert "SENTINEL" not in safe_error(RuntimeError("RAW_BODY_SENTINEL"))


def test_images_are_links_with_permission(entry_factory, monkeypatch):
    """只有独立图片许可和精确HTTPS主机同时满足才保留URL；过滤不产生出站。"""
    entry = entry_factory()
    entry.image_allowed, entry.image_hosts = False, {"images.example.org"}
    assert allowed_image("https://images.example.org/a.jpg", "Source", entry) == (None, None)
    entry.image_allowed = True
    assert allowed_image("https://images.example.org/a.jpg", "Source", entry) == (
        "https://images.example.org/a.jpg", "Source",
    )
    assert allowed_image("data:image/png;base64,AAAA", None, entry) == (None, None)
    assert allowed_image("https://127.0.0.1/a.jpg", None, entry) == (None, None)

    def network_forbidden(*args, **kwargs):
        raise AssertionError("图片过滤不得联网")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    allowed_image("https://images.example.org/b.jpg", None, entry)


@pytest.mark.parametrize("url", [
    "http://images.example.org/a.jpg", "https://images.example.org:444/a.jpg",
    "https://user:pass@images.example.org/a.jpg", "https://evilimages.example.org/a.jpg",
    "https://[::1]/a.jpg", "https://8.8.8.8/a.jpg",
    "https://images.example.org/\na.jpg", "https://images.example.org\\@evil.example/a.jpg",
    "https://images.example.org/" + "a" * 4097,
])
def test_image_url_boundary_is_exact_and_fail_closed(entry_factory, url):
    """协议、端口、凭据、后缀伪装、IP字面量、控制字符和超长URL都降级为无图。"""
    entry = entry_factory()
    entry.image_allowed, entry.image_hosts = True, {"images.example.org"}
    assert allowed_image(url, "credit", entry) == (None, None)


def test_image_credit_is_optional_bounded_metadata(entry_factory):
    """无效署名不影响已许可图片URL，且不截断或保存过长文本。"""
    entry = entry_factory()
    entry.image_allowed, entry.image_hosts = True, {"images.example.org"}
    assert allowed_image("https://images.example.org/a.jpg", " ", entry) == (
        "https://images.example.org/a.jpg", None,
    )
    assert allowed_image("https://images.example.org/a.jpg", "x" * 501, entry) == (
        "https://images.example.org/a.jpg", None,
    )
