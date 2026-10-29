"""已认证固定来源及各入口许可／运行状态只读 API。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DatabaseSession

from app.presentation.http.auth import require_session
from app.presentation.http.dependencies import get_db
from app.application.sources import SourceOut, sources_out


class SourceListOut(BaseModel):
    """固定网站列表容器；页面不能从此接口编辑或启停入口。"""

    items: list[SourceOut]


sources_router = APIRouter(dependencies=[Depends(require_session)])


@sources_router.get("/api/sources", name="source_list", response_model=SourceListOut)
def source_list(db: DatabaseSession = Depends(get_db)) -> SourceListOut:
    """分别返回入口许可和访问错误，不把网站 partial 当成本入口允许。"""
    return SourceListOut(items=sources_out(db))
