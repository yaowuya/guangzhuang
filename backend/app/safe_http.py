"""固定来源的 SSRF 目标验证；所有地址先验证，再只返回可固定连接的 IP。"""

from dataclasses import dataclass
import http.client
import ipaddress
import math
import multiprocessing
import socket
import ssl
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


class BlockedTarget(ValueError):
    """URL、DNS 或地址不满足固定公网出口规则。"""


@dataclass(frozen=True)
class Target:
    """一次解析后可用的固定连接目标；消费者不得再次按 host 解析。"""

    host: str
    port: int
    path: str
    ip: str


def _resolver_process(host: str, port: int, sender) -> None:
    """在可终止子进程中调用无原生超时的 getaddrinfo。"""
    try:
        addresses = [row[4][0] for row in socket.getaddrinfo(
            host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM,
        )]
        sender.send(("ok", addresses))
    except BaseException as error:  # 子进程只传异常类型，不传可能含输入的正文。
        try:
            sender.send(("error", type(error).__name__))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        sender.close()


def resolve_bounded(host: str, port: int, timeout: float = 5) -> list[str]:
    """用最多五秒的可回收子进程解析；超时 terminate/join，不遗留无限线程。"""
    try:
        budget = min(float(timeout), 5.0)
    except (TypeError, ValueError):
        raise BlockedTarget("DNS 解析超时配置无效") from None
    if budget <= 0:
        raise BlockedTarget("DNS 解析预算已耗尽")
    normalized_host = _host(host)
    if port != 443:
        raise BlockedTarget("DNS 解析端口不允许")
    try:
        ipaddress.ip_address(normalized_host)
    except ValueError:
        pass
    else:
        raise BlockedTarget("不允许解析 IP 字面量")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_resolver_process, args=(normalized_host, port, sender), daemon=True)
    try:
        process.start()
        sender.close()
        process.join(budget)
        if process.is_alive():
            process.terminate()
            process.join(1)
            if process.is_alive():
                process.kill()
                process.join()
            raise BlockedTarget("DNS 解析超时")
        if not receiver.poll():
            raise BlockedTarget("DNS 解析失败")
        status, payload = receiver.recv()
        if status != "ok" or not isinstance(payload, list):
            raise BlockedTarget("DNS 解析失败")
        return payload
    except (EOFError, OSError) as error:
        raise BlockedTarget("DNS 解析失败") from error
    finally:
        if process.is_alive():
            process.terminate()
            process.join()
        receiver.close()
        sender.close()


def _host(value: str) -> str:
    """将配置和 URL 主机规范到精确 IDNA ASCII，不提供后缀或通配匹配。"""
    if not value or any(ord(character) < 33 or ord(character) == 127 for character in value):
        raise BlockedTarget("目标主机无效")
    try:
        normalized = value.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise BlockedTarget("目标主机无效") from None
    if len(normalized) > 253 or normalized.startswith(".") or normalized.endswith("."):
        raise BlockedTarget("目标主机无效")
    labels = normalized.split(".")
    if len(labels) < 2 or any(
        not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
        or any(not (character.isascii() and (character.isalnum() or character == "-")) for character in label)
        for label in labels
    ):
        raise BlockedTarget("目标主机无效")
    return normalized


def validate_target(url: str, allowed_hosts, resolve) -> Target:
    """验证全部解析地址并返回固定 IP，阻止混合 DNS、重绑定和域名二次解析。"""
    if not isinstance(url, str) or not (1 <= len(url) <= 4096):
        raise BlockedTarget("目标 URL 长度无效")
    if "\\" in url or any(ord(character) < 32 or ord(character) == 127 for character in url):
        raise BlockedTarget("目标 URL 包含非法字符")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise BlockedTarget("目标 URL 无效") from None
    if parsed.scheme.lower() != "https" or port not in (None, 443):
        raise BlockedTarget("只允许 HTTPS 443")
    if parsed.username is not None or parsed.password is not None:
        raise BlockedTarget("目标 URL 不能包含凭据")
    host = _host(parsed.hostname or "")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise BlockedTarget("不允许 IP 字面量目标")
    normalized_allowed = {_host(str(candidate)) for candidate in allowed_hosts}
    if host not in normalized_allowed:
        raise BlockedTarget("目标主机不在固定范围")
    try:
        resolved = list(resolve(host, 443))
    except Exception as error:
        raise BlockedTarget("DNS 解析失败") from error
    if not resolved:
        raise BlockedTarget("DNS 未返回地址")
    addresses: list[str] = []
    for raw in resolved:
        if not isinstance(raw, str) or "%" in raw:
            raise BlockedTarget("DNS 返回地址无效")
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            raise BlockedTarget("DNS 返回地址无效") from None
        if (not address.is_global or address.is_multicast or address.is_unspecified
                or address.is_loopback or address.is_link_local or address.is_private
                or address.is_reserved or getattr(address, "ipv4_mapped", None) is not None):
            raise BlockedTarget("目标不是公网地址")
        canonical = str(address)
        if canonical not in addresses:
            addresses.append(canonical)
    encoded_path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    encoded_query = quote(parsed.query, safe="%:@!$&'()*+,;=/?-._~")
    path = urlunsplit(("", "", encoded_path, encoded_query, ""))
    return Target(host=host, port=443, path=path, ip=addresses[0])


class FetchError(RuntimeError):
    """安全请求的稳定失败类型；不携带响应正文或底层异常文本。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class Limits:
    """一次入口读取的连接、读取、总预算、体积与跳转硬上限。"""

    connect: float = 5
    read: float = 10
    total: float = 30
    max_bytes: int = 2 * 1024 * 1024
    max_redirects: int = 3

    def __post_init__(self) -> None:
        times = (self.connect, self.read, self.total)
        if (any(type(value) not in {int, float} or not math.isfinite(value) or value <= 0 for value in times)
                or type(self.max_bytes) is not int or self.max_bytes <= 0
                or type(self.max_redirects) is not int or not 0 <= self.max_redirects <= 10):
            raise ValueError("安全请求限制无效")


@dataclass(frozen=True)
class Fetched:
    """一次完整且未截断的允许媒体响应；不包含响应头或连接对象。"""

    final_url: str
    media_type: str
    body: bytes


class _PinnedResponse:
    def __init__(self, response: http.client.HTTPResponse, secure_socket) -> None:
        self.status = response.status
        headers: dict[str, str] = {}
        for key, value in response.getheaders():
            normalized = key.lower()
            headers[normalized] = f"{headers[normalized]},{value}" if normalized in headers else value
        self.headers = headers
        self._response = response
        self._socket = secure_socket

    def read(self, size: int, timeout: float) -> bytes:
        self._socket.settimeout(timeout)
        return self._response.read(size)

    def close(self) -> None:
        self._response.close()


class _PinnedConnection:
    def __init__(self, target: Target, secure_socket, timeout: float) -> None:
        self._target = target
        self._connection = http.client.HTTPConnection(target.host, target.port, timeout=timeout)
        self._connection.sock = secure_socket

    def request(self, path: str, headers: dict[str, str], timeout: float) -> _PinnedResponse:
        if path != self._target.path:
            raise FetchError("target_changed", "请求路径与已验证目标不一致")
        self._connection.sock.settimeout(timeout)
        self._connection.request("GET", path, headers=headers)
        response = self._connection.getresponse()
        return _PinnedResponse(response, self._connection.sock)

    def close(self) -> None:
        self._connection.close()


def pinned_dial(target: Target, timeout: float) -> _PinnedConnection:
    """socket 只连接 Target.ip，TLS SNI 与证书验证仍使用 Target.host。"""
    family = socket.AF_INET6 if ":" in target.ip else socket.AF_INET
    raw = socket.socket(family, socket.SOCK_STREAM)
    try:
        raw.settimeout(timeout)
        raw.connect((target.ip, target.port))
        secure = ssl.create_default_context().wrap_socket(raw, server_hostname=target.host)
        return _PinnedConnection(target, secure, timeout)
    except BaseException:
        raw.close()
        raise


class SafeClient:
    """无自动重试的固定 IP GET 客户端；每次跳转重新解析并验证全部地址。"""

    _REDIRECTS = {301, 302, 303, 307, 308}
    _MEDIA_TYPES = {
        "application/rss+xml", "application/rdf+xml", "application/xml", "text/xml",
        "text/html", "application/xhtml+xml",
    }

    def __init__(self, allowed_hosts, resolve, dial, limits: Limits | None = None) -> None:
        self.allowed_hosts = frozenset(allowed_hosts)
        self.resolve = resolve
        self.dial = dial
        self.limits = limits or Limits()

    @classmethod
    def from_spec(cls, entry) -> "SafeClient":
        """由已绑定固定入口构造生产客户端；不从浏览器或数据库错误字段取主机。"""
        return cls(entry.allowed_hosts, resolve_bounded, pinned_dial, Limits())

    def _remaining(self, deadline: float, local_limit: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError("timeout", "来源请求超过总时间预算")
        return min(remaining, local_limit)

    def _target(self, url: str, deadline: float) -> Target:
        dns_budget = self._remaining(deadline, 5)

        def budgeted(host: str, port: int):
            if self.resolve is resolve_bounded:
                return self.resolve(host, port, dns_budget)
            return self.resolve(host, port)

        try:
            target = validate_target(url, self.allowed_hosts, budgeted)
        except BlockedTarget:
            raise FetchError("blocked_target", "来源目标不符合安全策略") from None
        self._remaining(deadline, self.limits.total)
        return target

    @staticmethod
    def _close(resource) -> None:
        if resource is not None:
            try:
                resource.close()
            except Exception:
                pass

    def fetch(self, url: str) -> Fetched:
        """最多四次请求取得完整允许媒体；任何超限、截断或异常都整体失败。"""
        deadline = time.monotonic() + self.limits.total
        current = url
        visited: set[str] = set()
        for hop in range(self.limits.max_redirects + 1):
            if current in visited:
                raise FetchError("redirect_loop", "来源跳转形成循环")
            visited.add(current)
            target = self._target(current, deadline)
            connection = response = None
            try:
                connection = self.dial(target, self._remaining(deadline, self.limits.connect))
                headers = {
                    "Host": target.host,
                    "Accept": "application/rss+xml, application/xml, text/xml, text/html, application/xhtml+xml",
                    "Accept-Encoding": "identity",
                    "User-Agent": "PersonalHeadlineReader/1.0",
                    "Connection": "close",
                }
                response = connection.request(
                    target.path, headers, self._remaining(deadline, self.limits.read),
                )
                status = int(response.status)
                response_headers = {str(key).lower(): str(value).strip()
                                    for key, value in response.headers.items()}
                if status in self._REDIRECTS:
                    location = response_headers.get("location")
                    if hop >= self.limits.max_redirects:
                        raise FetchError("too_many_redirects", "来源跳转次数过多")
                    if (not location or len(location) > 4096 or "\\" in location
                            or any(ord(character) < 32 or ord(character) == 127 for character in location)):
                        raise FetchError("invalid_redirect", "来源跳转地址无效")
                    current = urljoin(current, location)
                    continue
                if status != 200:
                    raise FetchError("http_status", "来源返回非成功状态")
                encoding = response_headers.get("content-encoding", "identity").lower()
                if encoding not in {"", "identity"}:
                    raise FetchError("compressed_response", "来源响应压缩不被允许")
                media_type = response_headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if media_type not in self._MEDIA_TYPES:
                    raise FetchError("unsupported_media", "来源响应类型不被允许")
                declared: int | None = None
                length = response_headers.get("content-length")
                if length is not None:
                    if not length.isdigit():
                        raise FetchError("invalid_length", "来源响应长度无效")
                    declared = int(length)
                    if declared > self.limits.max_bytes:
                        raise FetchError("response_too_large", "来源响应超过体积上限")
                body = bytearray()
                while True:
                    size = min(64 * 1024, self.limits.max_bytes + 1 - len(body))
                    chunk = response.read(size, self._remaining(deadline, self.limits.read))
                    if not isinstance(chunk, bytes):
                        raise FetchError("invalid_response", "来源响应读取无效")
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > self.limits.max_bytes:
                        raise FetchError("response_too_large", "来源响应超过体积上限")
                if declared is not None and len(body) != declared:
                    raise FetchError("truncated_response", "来源响应长度与声明不一致")
                self._remaining(deadline, self.limits.total)
                return Fetched(final_url=current, media_type=media_type, body=bytes(body))
            except FetchError:
                raise
            except (TimeoutError, socket.timeout):
                raise FetchError("timeout", "来源请求超时") from None
            except ssl.SSLError:
                raise FetchError("tls_error", "来源 TLS 验证失败") from None
            except (OSError, http.client.HTTPException):
                raise FetchError("transport_error", "来源连接失败") from None
            finally:
                self._close(response)
                self._close(connection)
        raise FetchError("too_many_redirects", "来源跳转次数过多")
