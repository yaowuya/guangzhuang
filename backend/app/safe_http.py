"""固定来源的 SSRF 目标验证；所有地址先验证，再只返回可固定连接的 IP。"""

from dataclasses import dataclass
import ipaddress
import multiprocessing
import socket
from urllib.parse import urlsplit, urlunsplit


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
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return Target(host=host, port=443, path=path, ip=addresses[0])
