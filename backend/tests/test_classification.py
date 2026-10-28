"""只依据标题和栏目明示词的可追溯分类测试。"""

import json
import pytest

from app.classification import CATEGORY_CODES, classify, load_rules


def test_explicit_multilingual_rules():
    """中英日韩明确词命中，模糊公司动态保持完全未知。"""
    rules = load_rules("config/classification.json")
    assert "new_ingredients" in classify("New ingredient announced", None, rules).category_codes
    assert "regulation_compliance" in classify("化粧品規制の更新", None, rules).category_codes
    assert "new_products" in classify("신제품 출시", None, rules).category_codes
    unknown = classify("Company update", None, rules)
    assert (unknown.category_codes, unknown.region, unknown.product_type) == ((), None, None)


def test_all_categories_have_traceable_positive_examples_and_fixed_order():
    """每类都有明确可读词，命中顺序由产品七类固定而非 JSON 顺序决定。"""
    rules = load_rules("config/classification.json")
    examples = {
        "new_products": "New product launch",
        "trends": "Beauty market trend report",
        "new_ingredients": "新原料发布",
        "research_technology": "研发技术取得进展",
        "packaging_formulation": "New packaging formulation",
        "oem_odm": "OEM ODM manufacturing update",
        "regulation_compliance": "法规合规更新",
    }
    for code, title in examples.items():
        assert code in classify(title, None, rules).category_codes
    combined = classify("法规合规与新原料趋势", None, rules)
    assert combined.category_codes == tuple(code for code in CATEGORY_CODES if code in {
        "regulation_compliance", "new_ingredients", "trends",
    })


def test_market_and_product_require_explicit_unambiguous_evidence():
    """媒体名或公司国籍不推断市场；多个明确市场或品类冲突时保留未知。"""
    rules = load_rules("config/classification.json")
    assert classify("COSIN Korea company update", None, rules).region is None
    japan = classify("New serum launched in Japan", None, rules)
    assert (japan.region, japan.product_type) == ("日本", "护肤")
    conflict = classify("Skincare and hair care launch in Japan and Korea", None, rules)
    assert (conflict.region, conflict.product_type) == (None, None)


def test_section_is_used_but_never_body_or_unregistered_values(tmp_path):
    """栏目可作为明示依据；非法字段、类别和无法编译的模式不能进入规则集。"""
    rules = load_rules("config/classification.json")
    assert "packaging_formulation" in classify("Supplier update", "Packaging & formulation", rules).category_codes
    path = tmp_path / "rules.json"
    for data in (
        [{"field": "body", "pattern": "secret", "value": "x", "evidence": "bad"}],
        [{"field": "category", "pattern": "x", "value": "not-a-category", "evidence": "bad"}],
        [{"field": "category", "pattern": "(", "value": "trends", "evidence": "bad"}],
    ):
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError):
            load_rules(path)
