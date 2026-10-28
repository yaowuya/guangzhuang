"""获许可入口的图片边界与单入口标题采集事务。"""

import ipaddress
from urllib.parse import urlsplit


def _image_host(value: str) -> str | None:
    try:
        normalized = value.encode("idna").decode("ascii").lower()
    except (AttributeError, UnicodeError):
        return None
    labels = normalized.split(".")
    if len(labels) < 2 or normalized.endswith(".") or any(
        not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
        or any(not (character.isascii() and (character.isalnum() or character == "-")) for character in label)
        for label in labels
    ):
        return None
    return normalized


def allowed_image(url: str | None, credit: str | None, entry) -> tuple[str | None, str | None]:
    """只返回浏览器可直连的获许可外链；不下载、探测、代理、转存或内嵌图片。"""
    if getattr(entry, "image_allowed", False) is not True or not isinstance(url, str):
        return None, None
    candidate = url.strip()
    if not candidate or len(candidate) > 4096 or "\\" in candidate:
        return None, None
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        return None, None
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        return None, None
    if parsed.scheme.lower() != "https" or port not in (None, 443):
        return None, None
    if parsed.username is not None or parsed.password is not None or not parsed.hostname:
        return None, None
    host = _image_host(parsed.hostname)
    if host is None:
        return None, None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None, None
    allowed = {_image_host(value) for value in getattr(entry, "image_hosts", ())}
    if None in allowed or host not in allowed:
        return None, None
    safe_credit = None
    if isinstance(credit, str):
        stripped = credit.strip()
        if (stripped and len(stripped) <= 500
                and not any(ord(character) < 32 or ord(character) == 127 for character in stripped)):
            safe_credit = stripped
    return candidate, safe_credit
