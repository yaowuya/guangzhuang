"""以可审查的标题／栏目正则产生受控分类；不读取正文或调用模型。"""

from dataclasses import dataclass
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
