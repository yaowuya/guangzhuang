"""RSS/RDF 与固定列表解析的元信息白名单测试。"""

from datetime import date

import pytest

from app.parsers import ParseError, parse_rss


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
    assert batch.skipped == {"invalid_url": 1, "missing_title": 1}


@pytest.mark.parametrize("raw", [
    b"<!DOCTYPE rss [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><rss><channel><item><title>&xxe;</title></item></channel></rss>",
    b"<rss><channel><item></rss>",
    b"<html><body><item><title>Not RSS</title></item></body></html>",
])
def test_rss_rejects_dtd_entities_malformed_and_unknown_structures(entry_factory, raw):
    """DTD、实体、畸形 XML 或非 RSS 结构是解析失败，不伪装成合法零条。"""
    with pytest.raises(ParseError):
        parse_rss(raw, entry_factory(kind="rss"))


def test_valid_empty_channel_is_zero_not_parse_failure(entry_factory):
    """结构正确的空 channel 可以成功返回零条。"""
    batch = parse_rss(b"<rss><channel><title>Unit feed</title></channel></rss>",
                      entry_factory(kind="rss"))
    assert batch.headlines == []
    assert batch.skipped == {}
