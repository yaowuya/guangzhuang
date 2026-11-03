"""固定目标解析、SSRF 拒绝与后续有界传输测试。"""

import pytest

from app.infrastructure.http.safe_client import (
    BlockedTarget, FetchError, Limits, SafeClient, resolve_bounded, validate_target,
)


def test_pinned_redirect_and_limits(http_lab):
    """每一跳都固定已验证 IP；最终响应超过上限时整体失败而非截断成功。"""
    http_lab.reply("https://allowed.example/a", status=302,
                   headers={"Location": "https://allowed.example/b"})
    http_lab.reply("https://allowed.example/b", body=b"x" * 17)
    client = SafeClient({"allowed.example"}, http_lab.resolve, http_lab.dial,
                        Limits(max_bytes=16))
    with pytest.raises(FetchError):
        client.fetch("https://allowed.example/a")
    assert all(connection.ip == "8.8.8.8" and connection.host == "allowed.example"
               for connection in http_lab.connections)
    assert len(http_lab.connections) == 2


def test_success_headers_media_and_second_dns_resolution(http_lab):
    """相同主机跳转仍重新解析；请求禁压缩并保留 Host，最终只返回完整允许媒体。"""
    http_lab.answers["allowed.example"] = [["8.8.8.8"], ["1.1.1.1"]]
    http_lab.reply("https://allowed.example/a", status=302, headers={"Location": "/b"})
    http_lab.reply("https://allowed.example/b", headers={
        "Content-Type": "text/html; charset=utf-8",
    }, body=b"<title>unit</title>")
    fetched = SafeClient({"allowed.example"}, http_lab.resolve, http_lab.dial).fetch(
        "https://allowed.example/a")
    assert (fetched.final_url, fetched.media_type, fetched.body) == (
        "https://allowed.example/b", "text/html", b"<title>unit</title>",
    )
    assert [target.ip for target in http_lab.connections] == ["8.8.8.8", "1.1.1.1"]
    for _, headers in http_lab.requests:
        assert headers["Host"] == "allowed.example"
        assert headers["Accept-Encoding"] == "identity"
        assert headers["User-Agent"] == "PersonalHeadlineReader/1.0"


def test_private_redirect_loop_and_redirect_budget_are_rejected(http_lab):
    """跳转目标逐跳重验，循环和第4次跳转都不能继续请求。"""
    http_lab.reply("https://allowed.example/a", status=302,
                   headers={"Location": "https://private.example/x"})
    http_lab.answers["private.example"] = ["10.0.0.1"]
    client = SafeClient({"allowed.example", "private.example"}, http_lab.resolve, http_lab.dial)
    with pytest.raises(FetchError) as private:
        client.fetch("https://allowed.example/a")
    assert private.value.code == "blocked_target"
    assert len(http_lab.connections) == 1

    loop_lab = type(http_lab)()
    loop_lab.reply("https://allowed.example/a", status=302, headers={"Location": "/b"})
    loop_lab.reply("https://allowed.example/b", status=302, headers={"Location": "/a"})
    with pytest.raises(FetchError) as loop:
        SafeClient({"allowed.example"}, loop_lab.resolve, loop_lab.dial).fetch("https://allowed.example/a")
    assert loop.value.code == "redirect_loop"

    budget_lab = type(http_lab)()
    for index in range(5):
        budget_lab.reply(f"https://allowed.example/{index}", status=302,
                         headers={"Location": f"/{index + 1}"})
    with pytest.raises(FetchError) as budget:
        SafeClient({"allowed.example"}, budget_lab.resolve, budget_lab.dial).fetch(
            "https://allowed.example/0")
    assert budget.value.code == "too_many_redirects"
    assert len(budget_lab.connections) == 4


@pytest.mark.parametrize(("headers", "body", "code"), [
    ({"Content-Encoding": "gzip"}, b"x", "compressed_response"),
    ({"Content-Type": "application/octet-stream"}, b"x", "unsupported_media"),
    ({"Content-Length": "invalid"}, b"x", "invalid_length"),
    ({"Content-Length": "10"}, b"abc", "truncated_response"),
    ({"Content-Length": None}, b"x" * 17, "response_too_large"),
])
def test_response_encoding_type_length_and_chunk_limits(http_lab, headers, body, code):
    """声明和实际读取都受限；不接受压缩、未知媒体或截断结果。"""
    http_lab.reply("https://allowed.example/a", headers=headers, body=body)
    with pytest.raises(FetchError) as error:
        SafeClient({"allowed.example"}, http_lab.resolve, http_lab.dial,
                   Limits(max_bytes=16)).fetch("https://allowed.example/a")
    assert error.value.code == code


def test_non_success_and_invalid_redirect_are_safe_errors(http_lab):
    """非200和含控制字符的 Location 不读取正文或泄漏状态细节。"""
    http_lab.reply("https://allowed.example/a", status=503, body=b"private upstream body")
    with pytest.raises(FetchError) as status:
        SafeClient({"allowed.example"}, http_lab.resolve, http_lab.dial).fetch(
            "https://allowed.example/a")
    assert status.value.code == "http_status"
    assert "private" not in str(status.value)

    redirect_lab = type(http_lab)()
    redirect_lab.reply("https://allowed.example/a", status=302,
                       headers={"Location": "https://allowed.example/\nsecret"})
    with pytest.raises(FetchError) as redirect:
        SafeClient({"allowed.example"}, redirect_lab.resolve, redirect_lab.dial).fetch(
            "https://allowed.example/a")
    assert redirect.value.code == "invalid_redirect"


@pytest.mark.parametrize("changes", [
    {"connect": float("nan")}, {"read": 0}, {"total": float("inf")},
    {"max_bytes": True}, {"max_redirects": -1},
])
def test_invalid_limits_are_rejected(changes):
    """NaN、无穷、布尔体积和非正预算不能绕过边界计算。"""
    with pytest.raises(ValueError):
        Limits(**changes)


def test_no_retry_and_total_budget(http_lab, monkeypatch):
    """连接失败只尝试一次；总预算覆盖解析、连接和读取各阶段。"""
    client = SafeClient({"allowed.example"}, http_lab.resolve, http_lab.dial)
    with pytest.raises(FetchError) as missing:
        client.fetch("https://allowed.example/missing")
    assert missing.value.code == "transport_error"
    assert len(http_lab.connections) == 1

    from app.infrastructure.http import safe_client as safe_http
    moments = iter([0.0, 0.05, 0.10, 0.15, 0.21])
    monkeypatch.setattr(safe_http.time, "monotonic", lambda: next(moments, 0.21))
    timed_lab = type(http_lab)()
    timed_lab.reply("https://allowed.example/a", body=b"x")
    with pytest.raises(FetchError) as timed:
        SafeClient({"allowed.example"}, timed_lab.resolve, timed_lab.dial,
                   Limits(total=0.2)).fetch("https://allowed.example/a")
    assert timed.value.code == "timeout"


def test_pinned_dial_connects_ip_but_uses_hostname_for_sni(monkeypatch):
    """生产拨号不让 HTTP 库重新解析域名，证书和 SNI 仍绑定原主机。"""
    from app.infrastructure.http import safe_client as safe_http

    events = []

    class RawSocket:
        def settimeout(self, timeout):
            events.append(("timeout", timeout))

        def connect(self, address):
            events.append(("connect", address))

        def close(self):
            events.append("raw-close")

    class SecureSocket:
        def close(self):
            events.append("secure-close")

    class Context:
        def wrap_socket(self, raw, server_hostname):
            events.append(("sni", server_hostname))
            return SecureSocket()

    monkeypatch.setattr(safe_http.socket, "socket", lambda family, kind: RawSocket())
    monkeypatch.setattr(safe_http.ssl, "create_default_context", lambda: Context())
    connection = safe_http.pinned_dial(
        safe_http.Target("allowed.example", 443, "/a", "8.8.8.8"), 3)
    connection.close()
    assert ("connect", ("8.8.8.8", 443)) in events
    assert ("sni", "allowed.example") in events


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
    assert target.path == "/%E8%B7%AF%E5%BE%84"


def test_resolver_process_reports_invalid_input_without_leaking_children():
    """生产解析子进程异常有界返回，不遗留无限线程或把异常文本当地址。"""
    with pytest.raises(BlockedTarget):
        resolve_bounded("\0", 443, timeout=1)


def test_resolver_timeout_terminates_and_joins_process(monkeypatch):
    """超时路径必须 terminate/join，不能用不可回收线程包装 getaddrinfo。"""
    from app.infrastructure.http import safe_client as safe_http

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
