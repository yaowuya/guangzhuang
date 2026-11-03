"""HTTP 查询参数到应用层 ArticleQuery 的严格适配。"""

from datetime import date
import re

from app.application.articles import ArticleQuery
from app.core.exceptions import ApiError
from app.domain.classification import CATEGORY_CODES


def _query_pairs(mapping) -> list[tuple[str, str]]:
    if hasattr(mapping, "multi_items"):
        return list(mapping.multi_items())
    if hasattr(mapping, "items"):
        return [(str(key), str(value)) for key, value in mapping.items()]
    return [(str(key), str(value)) for key, value in mapping]


def _date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError
    return date.fromisoformat(value)


def parse_query(mapping) -> ArticleQuery:
    """严格解析单值查询；重复、未知或超界参数都拒绝，不能静默扩成全库。"""
    allowed = {"q", "category", "region", "product_type", "date_from", "date_to", "page", "page_size"}
    seen: set[str] = set()
    values: dict[str, object] = {}
    try:
        for key, raw in _query_pairs(mapping):
            if key not in allowed or key in seen:
                raise ValueError
            seen.add(key)
            if key in {"page", "page_size"}:
                if not re.fullmatch(r"[1-9]\d*", raw):
                    raise ValueError
                number = int(raw)
                if number > 2_147_483_647 or (key == "page_size" and number > 100):
                    raise ValueError
                values[key] = number
            elif key == "q":
                if len(raw) > 200:
                    raise ValueError
                if raw:
                    values[key] = raw
            elif key == "category":
                if raw != "__uncategorized__" and raw not in CATEGORY_CODES:
                    raise ValueError
                values[key] = raw
            elif key in {"region", "product_type"}:
                if not raw or len(raw) > 100:
                    raise ValueError
                values[key] = raw
            else:
                values[key] = _date(raw)
        query = ArticleQuery(**values)
        if query.date_from and query.date_to and query.date_from > query.date_to:
            raise ValueError
        return query
    except (TypeError, ValueError):
        raise ApiError("invalid_filter", "筛选条件无效", 400) from None
