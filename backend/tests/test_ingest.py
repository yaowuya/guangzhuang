"""图片外链边界与单入口采集事务测试。"""

import socket

import pytest

from app.ingest import allowed_image


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
