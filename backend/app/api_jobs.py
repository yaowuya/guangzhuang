"""更新任务的入队、重试、当前状态与详情 HTTP 契约。"""

from typing import Literal

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DatabaseSession

from .api_auth import AuthenticatedSession, require_session, require_write
from .database import get_db
from .errors import ApiError
from .jobs import JobOut, current_job, enqueue_refresh, job_out, retry_job
from .models import UpdateJob


class RefreshIn(BaseModel):
    """MVP 只允许用户触发 refresh，不接收来源或调度参数。"""

    model_config = ConfigDict(extra="forbid")
    trigger: Literal["refresh"]


class EmptyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnqueueOut(BaseModel):
    job: JobOut
    reused: bool


class CurrentJobOut(BaseModel):
    job: JobOut | None


jobs_router = APIRouter()


def _enqueue_response(db: DatabaseSession, result) -> JSONResponse:
    output = EnqueueOut(job=job_out(db, result.job), reused=result.reused)
    return JSONResponse(output.model_dump(mode="json"), status_code=200 if result.reused else 202)


@jobs_router.get(
    "/api/update-jobs/current", name="job_current", response_model=CurrentJobOut,
    dependencies=[Depends(require_session)],
)
def job_current(db: DatabaseSession = Depends(get_db)) -> CurrentJobOut:
    """活动优先，否则返回最近任务；从未更新时明确返回 null。"""
    return CurrentJobOut(job=current_job(db))


@jobs_router.post("/api/update-jobs", name="job_create", response_model=EnqueueOut)
def job_create(
    request: Request,
    body: RefreshIn,
    db: DatabaseSession = Depends(get_db),
    authenticated: AuthenticatedSession = Depends(require_write),
):
    """只提交持久任务并立即响应，不在 API 线程执行来源请求。"""
    del body, authenticated
    return _enqueue_response(db, enqueue_refresh(db, request.app.state.now()))


@jobs_router.post("/api/update-jobs/{job_id}/retry", name="job_retry", response_model=EnqueueOut)
def job_retry(
    request: Request,
    body: EmptyIn,
    job_id: int = Path(gt=0),
    db: DatabaseSession = Depends(get_db),
    authenticated: AuthenticatedSession = Depends(require_write),
):
    """只为原失败/中断且当前可用入口入队，活动任务则复用。"""
    del body, authenticated
    return _enqueue_response(db, retry_job(db, job_id, request.app.state.now()))


@jobs_router.get(
    "/api/update-jobs/{job_id}", name="job_detail", response_model=JobOut,
    dependencies=[Depends(require_session)],
)
def job_detail(
    job_id: int = Path(gt=0),
    db: DatabaseSession = Depends(get_db),
) -> JobOut:
    """返回持久任务和各入口结果；不存在使用稳定 404。"""
    job = db.get(UpdateJob, job_id)
    if job is None:
        raise ApiError("job_not_found", "任务不存在", 404)
    return job_out(db, job)
