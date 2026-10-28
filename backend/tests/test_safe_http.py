"""固定目标解析、SSRF 拒绝与后续有界传输测试。"""

import pytest

from app.safe_http import BlockedTarget, resolve_bounded, validate_target


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.1.1.1", "169.254.169.254", "100.64.0.1",
    "::1", "fe80::1", "192.0.2.1", "::ffff:127.0.0.1", "224.0.0.1", "ff02::1",
])
def test_reject_reserved_and_rebinding(ip):
    """任一混合解析结果非公网就整体拒绝，不能挑一个公网地址继续。"""
    with pytest.raises(BlockedTarget):
        validate_target(
            "https://allowed.example/feed", {"allowed.example"},
            lambda host, port: ["8.8.8.8", ip],
        )
    target = validate_target(
        "https://allowed.example/feed?q=1", {"allowed.example"},
        lambda host, port: ["8.8.8.8"],
    )
    assert (target.ip, target.host, target.port, target.path) == (
        "8.8.8.8", "allowed.example", 443, "/feed?q=1",
    )


@pytest.mark.parametrize("url", [
    "http://allowed.example/feed", "https://allowed.example:444/feed",
    "https://user:pass@allowed.example/feed", "https://evilallowed.example/feed",
    "https://8.8.8.8/feed", "https://allowed.example\\@evil.example/feed",
    "https://allowed.example/\nfeed", "https://allowed.example/" + "x" * 4097,
    "https://singlelabel/feed", "https://bad_host.example/feed",
])
def test_reject_invalid_literal_and_allowlist_bypasses(url):
    """协议、端口、凭据、后缀伪装、IP 字面量和控制字符均在解析前失败关闭。"""
    called = False

    def resolver(host, port):
        nonlocal called
        called = True
        return ["8.8.8.8"]

    with pytest.raises(BlockedTarget):
        validate_target(url, {"allowed.example"}, resolver)
    assert called is False


def test_empty_duplicate_or_failed_resolution_is_closed():
    """解析异常、空结果和无效地址不能回退到域名重连。"""
    with pytest.raises(BlockedTarget):
        validate_target("https://allowed.example/", {"allowed.example"}, lambda host, port: [])
    with pytest.raises(BlockedTarget):
        validate_target("https://allowed.example/", {"allowed.example"},
                        lambda host, port: (_ for _ in ()).throw(OSError("unit dns")))
    target = validate_target("https://allowed.example/", {"allowed.example"},
                             lambda host, port: ["8.8.8.8", "8.8.8.8"])
    assert target.ip == "8.8.8.8"


def test_idna_host_and_public_ipv6_are_canonicalized():
    """Unicode 主机按 IDNA 精确匹配，公网 IPv6 保留规范地址供固定连接。"""
    seen = []
    target = validate_target(
        "https://例子.测试/路径", {"例子.测试"},
        lambda host, port: seen.append((host, port)) or ["2606:4700:4700::1111"],
    )
    assert seen == [("xn--fsqu00a.xn--0zwm56d", 443)]
    assert target.host == "xn--fsqu00a.xn--0zwm56d"
    assert target.ip == "2606:4700:4700::1111"


def test_resolver_process_reports_invalid_input_without_leaking_children():
    """生产解析子进程异常有界返回，不遗留无限线程或把异常文本当地址。"""
    with pytest.raises(BlockedTarget):
        resolve_bounded("\0", 443, timeout=1)


def test_resolver_timeout_terminates_and_joins_process(monkeypatch):
    """超时路径必须 terminate/join，不能用不可回收线程包装 getaddrinfo。"""
    from app import safe_http

    events = []

    class PipeEnd:
        def close(self):
            events.append("close")

        def poll(self):
            return False

    class Process:
        alive = True

        def start(self):
            events.append("start")

        def join(self, timeout=None):
            events.append(("join", timeout))

        def is_alive(self):
            return self.alive

        def terminate(self):
            events.append("terminate")
            self.alive = False

        def kill(self):
            events.append("kill")
            self.alive = False

    class Context:
        def Pipe(self, duplex=False):
            return PipeEnd(), PipeEnd()

        def Process(self, **kwargs):
            return Process()

    monkeypatch.setattr(safe_http.multiprocessing, "get_context", lambda mode: Context())
    with pytest.raises(BlockedTarget, match="超时"):
        resolve_bounded("allowed.example", 443, timeout=0.01)
    assert "terminate" in events
    assert "kill" not in events
    assert any(isinstance(event, tuple) and event[0] == "join" for event in events)
