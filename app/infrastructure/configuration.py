"""受控本地配置文件适配器。"""

import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import uuid4

from app.domain.classification import CATEGORY_CODES, Rule
from app.domain.sources import CANDIDATES, EntrySpec, validate_entry_identity

_ALLOWED_FIELDS = {"category", "region", "product_type"}


def load_rules(path: str | Path) -> list[Rule]:
    """读取并验证固定分类规则，不接受正文或任意分类字段。"""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("分类规则不可读取") from error
    if not isinstance(raw, list):
        raise ValueError("分类规则必须为数组")
    rules = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"field", "pattern", "value", "evidence"}:
            raise ValueError("分类规则字段不完整")
        if not all(isinstance(item[name], str) and item[name].strip() for name in item):
            raise ValueError("分类规则字段不能为空")
        if (item["field"] not in _ALLOWED_FIELDS or len(item["pattern"]) > 200
                or len(item["value"]) > 100 or len(item["evidence"]) > 500):
            raise ValueError("分类规则超出允许边界")
        if item["field"] == "category" and item["value"] not in CATEGORY_CODES:
            raise ValueError("类别代码不在固定七类中")
        try:
            re.compile(item["pattern"])
        except re.error as error:
            raise ValueError("分类规则正则无效") from error
        rules.append(Rule(**item))
    return rules


_REGISTRY_FIELDS = {
    "key", "source_key", "source_name", "language", "url", "kind", "allowed_hosts",
    "image_hosts", "image_allowed", "verification_status", "verification_reason",
    "verification_reference", "enabled", "selection",
}
_SELECTION_FIELDS = {
    "container", "item", "title", "link", "empty", "date", "section", "image", "credit", "date_format",
}


def load_registry(path: str | Path) -> list[EntrySpec]:
    """读取并验证唯一候选清单；拒绝动态 provider 和配置内伪造许可。"""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("来源配置不可读取") from error
    if not isinstance(raw, list) or len(raw) != len(CANDIDATES):
        raise ValueError("来源清单必须为固定五站六入口")
    specs: list[EntrySpec] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) != _REGISTRY_FIELDS:
            raise ValueError("来源配置字段不完整或包含未注册字段")
        expected = CANDIDATES[index]
        identity = (item.get("key"), item.get("source_key"), item.get("url"), item.get("kind"))
        if identity != expected or item.get("kind") not in {"rss", "public_list"}:
            raise ValueError("来源身份不属于固定候选")
        if not isinstance(item.get("source_name"), str) or not item["source_name"].strip():
            raise ValueError("来源名称无效")
        if item.get("language") is not None and not isinstance(item["language"], str):
            raise ValueError("来源语言无效")
        if item.get("verification_status") != "pending" or item.get("enabled") is not False:
            raise ValueError("静态候选不能预先声明获许可或启用")
        if item.get("verification_reason") is not None or item.get("verification_reference") is not None:
            raise ValueError("入口许可必须来自独立核验证据")
        if not isinstance(item.get("allowed_hosts"), list) or not item["allowed_hosts"]:
            raise ValueError("来源主机白名单缺失")
        if any(not isinstance(host, str) or not host for host in item["allowed_hosts"]):
            raise ValueError("来源主机白名单无效")
        if urlsplit(item["url"]).hostname not in item["allowed_hosts"]:
            raise ValueError("候选 URL 不在自身固定主机范围")
        if not isinstance(item.get("image_hosts"), list) or any(
            not isinstance(host, str) or not host for host in item["image_hosts"]
        ):
            raise ValueError("图片主机列表无效")
        if not isinstance(item.get("image_allowed"), bool):
            raise ValueError("图片许可标记无效")
        if item["image_allowed"] and not item["image_hosts"]:
            raise ValueError("允许图片时必须有独立主机范围")
        selection = item.get("selection")
        if selection is not None:
            if not isinstance(selection, dict) or not set(selection) <= _SELECTION_FIELDS:
                raise ValueError("列表选择器字段无效")
            if not {"container", "item", "title", "link"} <= set(selection):
                raise ValueError("列表选择器缺少必要字段")
            if any(value is not None and not isinstance(value, str) for value in selection.values()):
                raise ValueError("列表选择器值无效")
        spec = EntrySpec(
            key=item["key"], source_key=item["source_key"], source_name=item["source_name"],
            language=item["language"], url=item["url"], kind=item["kind"],
            allowed_hosts=tuple(item["allowed_hosts"]), image_hosts=tuple(item["image_hosts"]),
            image_allowed=item["image_allowed"], verification_status="pending",
            verification_reason=None, verification_reference=None, enabled=False,
            selection=selection,
        )
        validate_entry_identity(spec)
        specs.append(spec)
    return specs


def _reject_private(value, path: str = "evidence") -> None:
    private = {"body", "content", "html"}
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if (normalized in private or normalized.startswith("raw_")
                    or any(marker in normalized for marker in ("password", "cookie", "csrf", "token"))):
                raise ValueError(f"核验证据包含私密或原始内容字段：{path}.{key}")
            _reject_private(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_private(nested, f"{path}[{index}]")
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError("核验证据包含不可序列化值")


def read_evidence(path: str | Path) -> dict:
    """读取有界安全 JSON 结论；不接受 Cookie、密码或原始网页载荷。"""
    target = Path(path)
    try:
        if target.stat().st_size > 128 * 1024:
            raise ValueError("核验证据文件过大")
        report = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("核验证据不可读取") from error
    if not isinstance(report, dict):
        raise ValueError("核验证据必须为对象")
    _reject_private(report)
    return report


def write_evidence(path: str | Path, report: dict) -> None:
    """原子保存安全 JSON 结论；失败时不覆盖上一份可复核证据。"""
    if not isinstance(report, dict):
        raise ValueError("核验证据必须为对象")
    _reject_private(report)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
