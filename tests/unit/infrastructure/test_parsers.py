"""RSS/RDF 与固定列表解析的元信息白名单测试。"""

from datetime import date

import pytest

from app.infrastructure.feeds.parsers import ListSelection, ParseError, parse_list, parse_rss


def test_rss_metadata_only(entry_factory):
    """description 和 content 只经过内存，不进入标题对象、跳过信息或 repr。"""
    entry = entry_factory(kind="rss")
    raw = b"""<rss><channel><item><title>Valid title</title>
      <link>https://example.org/a</link><description>CONTENT_SENTINEL</description>
      </item><item><title>Missing link</title></item></channel></rss>"""
    batch = parse_rss(raw, entry)
    assert len(batch.headlines) == 1
    assert batch.headlines[0].reported_date is None
    assert batch.skipped["missing_url"] == 1
    assert "CONTENT_SENTINEL" not in repr(batch)


def test_rss2_dates_sections_and_explicit_image_metadata(entry_factory):
    """只读取 RSS 明示日期、栏目、thumbnail/enclosure 与署名，不扫描 description HTML。"""
    entry = entry_factory(kind="rss")
    raw = b"""<?xml version='1.0'?>
    <rss xmlns:media='http://search.yahoo.com/mrss/' xmlns:content='http://purl.org/rss/1.0/modules/content/'>
      <channel>
        <item><title>Product launch</title><link>https://example.org/a</link>
          <pubDate>Thu, 01 Jan 2026 12:00:00 +0900</pubDate><category>New products</category>
          <media:thumbnail url='https://img.example.org/a.jpg'/><media:credit>UNIT credit</media:credit>
          <description><![CDATA[<img src='https://evil.example/private.jpg'>BODY_SENTINEL]]></description>
          <content:encoded>CONTENT_MODULE_SENTINEL</content:encoded>
        </item>
        <item><title>Bad date remains useful</title><link>https://example.org/b</link>
          <pubDate>not-a-date</pubDate><enclosure url='https://img.example.org/b.jpg' type='image/jpeg'/>
        </item>
      </channel>
    </rss>"""
    batch = parse_rss(raw, entry)
    assert [headline.reported_date for headline in batch.headlines] == [date(2026, 1, 1), None]
    assert batch.headlines[0].section == "New products"
    assert batch.headlines[0].image_url == "https://img.example.org/a.jpg"
    assert batch.headlines[0].image_credit == "UNIT credit"
    assert batch.headlines[1].image_url == "https://img.example.org/b.jpg"
    assert batch.skipped["invalid_date"] == 1
    assert "SENTINEL" not in repr(batch)


def test_rdf_dc_date_and_malicious_rows(entry_factory):
    """RSS 1.0/RDF 的 DC 日期可读，危险协议、缺标题和过长字段逐条跳过。"""
    entry = entry_factory(kind="rss")
    raw = b"""<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
      xmlns='http://purl.org/rss/1.0/' xmlns:dc='http://purl.org/dc/elements/1.1/'>
      <item><title>RDF title</title><link>https://example.org/rdf</link><dc:date>2026-02-03T10:00:00Z</dc:date></item>
      <item><title>Bad link</title><link>javascript:alert(1)</link></item>
      <item><link>https://example.org/no-title</link></item>
    </rdf:RDF>"""
    batch = parse_rss(raw, entry)
    assert [(headline.title, headline.reported_date) for headline in batch.headlines] == [
        ("RDF title", date(2026, 2, 3)),
    ]
    assert batch.skipped == {"unsafe_url": 1, "missing_title": 1}


@pytest.mark.parametrize("raw", [
    b"<!DOCTYPE rss [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><rss><channel><item><title>&xxe;</title></item></channel></rss>",
    b"<rss><channel><item></rss>",
    b"<html><body><item><title>Not RSS</title></item></body></html>",
])
def test_rss_rejects_dtd_entities_malformed_and_unknown_structures(entry_factory, raw):
    """DTD、实体、畸形 XML 或非 RSS 结构是解析失败，不伪装成合法零条。"""
    with pytest.raises(ParseError):
        parse_rss(raw, entry_factory(kind="rss"))


def test_public_list_has_no_detail_fetch(entry_factory):
    """只消费列表节点和相对链接，不解释脚本，也没有详情请求依赖。"""
    entry = entry_factory(kind="public_list", url="https://example.org/news/")
    entry.selection = ListSelection(container="ul.feed", item="li.news", title="a.title", link="a.title")
    raw = b"""<ul class='feed'><li class='news'><a class='title' href='/a'>A title</a></li></ul>
      <script>DETAIL_FETCH_SENTINEL()</script>"""
    batch = parse_list(raw, entry)
    assert [headline.title for headline in batch.headlines] == ["A title"]
    assert batch.headlines[0].original_url == "https://example.org/a"
    assert not hasattr(batch.headlines[0], "body")
    assert "SENTINEL" not in repr(batch)


def test_public_list_fixed_metadata_and_explicit_empty(entry_factory):
    """日期、栏目、图片和署名只来自固定选择器；明确空标记才允许零条。"""
    entry = entry_factory(kind="public_list", url="https://example.org/list/")
    entry.selection = ListSelection(
        container="main.feed", item="article.card", title="h2", link="a.read",
        empty="p.empty", date="time", section="span.section", image="img.thumb",
        credit="span.credit", date_format="%Y/%m/%d",
    )
    raw = b"""<main class='feed'><article class='card'>
      <h2>List title</h2><a class='read' href='item/1'>Read</a><time>2026/02/03</time>
      <span class='section'>Research</span><img class='thumb' src='/images/1.jpg'>
      <span class='credit'>UNIT credit</span><div class='body'>BODY_SENTINEL</div>
      </article></main>"""
    batch = parse_list(raw, entry)
    headline = batch.headlines[0]
    assert (headline.reported_date, headline.section) == (date(2026, 2, 3), "Research")
    assert (headline.image_url, headline.image_credit) == (
        "https://example.org/images/1.jpg", "UNIT credit",
    )
    assert "BODY_SENTINEL" not in repr(batch)
    empty = parse_list(b"<main class='feed'><p class='empty'>No entries</p></main>", entry)
    assert empty.headlines == [] and empty.skipped == {}


def test_public_list_structure_changes_and_unverified_selection_fail(entry_factory):
    """未核验选择器、缺容器、无条目且无empty标记、非法CSS都不能伪装成合法空响应。"""
    entry = entry_factory(kind="public_list")
    for selection, raw in (
        (None, b"<ul></ul>"),
        (ListSelection("main", "article", "h2", "a"), b"<section></section>"),
        (ListSelection("main", "article", "h2", "a"), b"<main></main>"),
        (ListSelection("[", "article", "h2", "a"), b"<main></main>"),
    ):
        entry.selection = selection
        with pytest.raises(ParseError):
            parse_list(raw, entry)


def test_public_list_skips_bad_rows_without_leaving_container(entry_factory):
    """缺标题／链接和危险协议逐条计数，容器外匹配节点不会被读取。"""
    entry = entry_factory(kind="public_list", url="https://example.org/feed/")
    entry.selection = ListSelection("ul.feed", "li.news", "a.title", "a.title")
    raw = b"""<a class='title' href='/outside'>Outside</a><ul class='feed'>
      <li class='news'><a class='title' href='javascript:bad()'>Bad</a></li>
      <li class='news'><a href='/missing-title'>No selected title</a></li>
      <li class='news'><a class='title'>Missing link</a></li>
      <li class='news'><a class='title' href='/valid'>Valid</a></li></ul>"""
    batch = parse_list(raw, entry)
    assert [headline.title for headline in batch.headlines] == ["Valid"]
    assert batch.skipped == {"unsafe_url": 1, "missing_title": 1, "missing_url": 1}


def test_valid_empty_channel_is_zero_not_parse_failure(entry_factory):
    """结构正确的空 channel 可以成功返回零条。"""
    batch = parse_rss(b"<rss><channel><title>Unit feed</title></channel></rss>",
                      entry_factory(kind="rss"))
    assert batch.headlines == []
    assert batch.skipped == {}
