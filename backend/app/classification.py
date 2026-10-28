"""以可审查的标题／栏目正则产生受控分类；不读取正文或调用模型。"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata

CATEGORY_CODES = (
    "new_products", "trends", "new_ingredients", "research_technology",
    "packaging_formulation", "oem_odm", "regulation_compliance",
)
CATEGORY_LABELS = {
    "new_products": "新品发布",
    "trends": "趋势洞察",
    "new_ingredients": "新原料",
    "research_technology": "研发技术",
    "packaging_formulation": "包装与剂型",
    "oem_odm": "OEM／ODM",
    "regulation_compliance": "法规与合规",
}
_ALLOWED_FIELDS = {"category", "region", "product_type"}


@dataclass(frozen=True)
class Rule:
    """一条可追溯的明确词规则；evidence 说明为什么允许此映射。"""

    field: str
    pattern: str
    value: str
    evidence: str


@dataclass(frozen=True)
class Classification:
    """确定的七类及单一地区／品类；冲突或无证据时对应值为空。"""

    category_codes: tuple[str, ...]
    region: str | None
    product_type: str | None


def load_rules(path: str | Path) -> list[Rule]:
    """从固定本地 JSON 读取并完整验证规则；不允许正文或任意分类字段。"""
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
        if item["field"] not in _ALLOWED_FIELDS or len(item["pattern"]) > 200 or len(item["value"]) > 100 or len(item["evidence"]) > 500:
            raise ValueError("分类规则超出允许边界")
        if item["field"] == "category" and item["value"] not in CATEGORY_CODES:
            raise ValueError("类别代码不在固定七类中")
        try:
            re.compile(item["pattern"])
        except re.error as error:
            raise ValueError("分类规则正则无效") from error
        rules.append(Rule(**item))
    return rules


def classify(title: str, section: str | None, rules: list[Rule]) -> Classification:
    """只搜索明示栏目和标题；多个地区／品类冲突时保留未知而不猜测。"""
    text = unicodedata.normalize("NFKC", f"{section or ''}\n{title}").casefold()
    categories: set[str] = set()
    regions: set[str] = set()
    product_types: set[str] = set()
    for rule in rules:
        if not re.search(rule.pattern, text):
            continue
        if rule.field == "category":
            categories.add(rule.value)
        elif rule.field == "region":
            regions.add(rule.value)
        else:
            product_types.add(rule.value)
    return Classification(
        tuple(code for code in CATEGORY_CODES if code in categories),
        next(iter(regions)) if len(regions) == 1 else None,
        next(iter(product_types)) if len(product_types) == 1 else None,
    )
