"""固定五站六入口的身份和值对象规则。"""

from dataclasses import dataclass
from urllib.parse import urlsplit

CANDIDATES = (
    ("prtimes-rss", "prtimes", "https://prtimes.jp/index.rdf", "rss"),
    ("prtimes-beauty", "prtimes", "https://prtimes.jp/beauty/", "public_list"),
    ("happi-rss", "happi", "https://www.happi.com/feed/", "rss"),
    ("qingyan-list", "qingyan", "https://www.iqingyan.cn/", "public_list"),
    ("pbn-list", "pbn", "https://www.premiumbeautynews.com/en/", "public_list"),
    ("cosin-list", "cosin", "https://cosinkorea.com/", "public_list"),
)
CANDIDATE_MAP = {candidate[0]: candidate for candidate in CANDIDATES}
SITE_METADATA = {
    "prtimes": ("PR TIMES", "ja"),
    "happi": ("HAPPI", "en"),
    "qingyan": ("青眼", "zh-CN"),
    "pbn": ("Premium Beauty News", "en"),
    "cosin": ("COSIN Korea", "ko"),
}


@dataclass(frozen=True)
class EntrySpec:
    """一个固定入口的技术配置；许可结论和实际访问结果由独立证据管理。"""

    key: str
    source_key: str
    source_name: str
    language: str | None
    url: str
    kind: str
    allowed_hosts: tuple[str, ...]
    image_hosts: tuple[str, ...]
    image_allowed: bool
    verification_status: str
    verification_reason: str | None
    verification_reference: str | None
    enabled: bool
    selection: dict[str, str | None] | None


def validate_entry_identity(spec: EntrySpec) -> None:
    """入口身份、站点元数据与主机必须属于固定候选集合。"""
    expected = CANDIDATE_MAP.get(spec.key)
    if expected is None or (spec.key, spec.source_key, spec.url, spec.kind) != expected:
        raise ValueError("来源身份不属于固定候选")
    if (spec.source_name, spec.language) != SITE_METADATA[spec.source_key]:
        raise ValueError("来源站点名称或语言与固定候选不一致")
    if urlsplit(spec.url).hostname not in spec.allowed_hosts:
        raise ValueError("候选 URL 不在自身固定主机范围")
