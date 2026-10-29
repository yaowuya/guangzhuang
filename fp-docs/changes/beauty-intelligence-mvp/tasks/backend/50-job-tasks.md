## 任务接口与独立 worker 任务

- [x] **Task backend-023: 并发手动刷新只创建一个活动任务**

**Files:**
- Create: `backend/app/application/jobs.py`、`backend/tests/integration/persistence/test_jobs.py`

**Reasoning:**
- D-007、D-023、D-024 要求请求立即得到持久任务ID，活动唯一索引不是只在测试中存在。

**Depends on:** backend-004, backend-016

**Interfaces:**
- Consumes: I04、I16 eligible_entries。
- Produces: I23 EnqueueResult/enqueue_refresh/enqueue。
- Contract checks: 原子创建Job与EntryResult；已有活动直接返回；无enabled入口409；网络不在API执行。

**Step 1: Write the failing test**
```python
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from app.application.jobs import enqueue_refresh

def test_concurrent_refresh_reuses_active(db, entry_factory, now):
    entry_factory(enabled=True, verification_status='allowed',
                  verification_reason='测试许可', verification_reference='https://example.org/terms')
    def run():
        with Session(db.bind) as other:
            return enqueue_refresh(other, now).job.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: run(), range(2)))
    assert len(set(ids)) == 1
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_jobs.py::test_concurrent_refresh_reuses_active -q`
- Expected: enqueue函数缺失。

**Step 3: Write minimal implementation**
```python
def enqueue_refresh(db, now):
    """只创建数据库任务；已有活动优先返回，不等待来源网络。"""
    active = db.scalar(select(UpdateJob).where(UpdateJob.state.in_(['pending', 'running'])))
    if active is not None:
        return EnqueueResult(active, True)
    ids = [e.id for e in eligible_entries(db)]
    if not ids:
        raise ApiError('no_enabled_sources', '没有已核验且启用的入口', 409)
    return enqueue(db, 'refresh', ids, None, now)
```
- enqueue在短事务写入Job(active_key=1)与唯一EntryResults；捕获活动唯一冲突后rollback并重查同一活动Job。日期唯一冲突仅供内部日程返回当日记录，不伪装成新任务。测试无网络调用、pending/running均复用、终态允许新建。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_jobs.py::test_concurrent_refresh_reuses_active -q`
- Expected: PASS。自审并发异常分支不会遗留半个任务或重复入口结果。

**Step 5: Commit**
```bash
git add backend/app/application/jobs.py backend/tests/integration/persistence/test_jobs.py
git commit -m "feat: enqueue one persistent active refresh"
```

- [x] **Task backend-024: 重试只选择原任务失败或中断且仍可用的入口**

**Files:**
- Extend planned: `backend/app/application/jobs.py`、`backend/tests/integration/persistence/test_jobs.py`

**Reasoning:**
- D-023、D-030 不得在重试中再次采集已成功入口，也不能绕过新近禁用或撤销的许可。

**Depends on:** backend-023

**Interfaces:**
- Consumes: I23、I16。
- Produces: I24 retry_job。
- Contract checks: failed/interrupted交eligible；成功/pending/running不作为手动重试候选；不存在404、空候选409。

**Step 1: Write the failing test**
```python
from app.application.jobs import retry_job

def test_retry_only_unsuccessful_eligible_entries(db, job_factory, entry_factory, now):
    entries = [entry_factory(enabled=True, verification_status='allowed',
               verification_reason='测试许可', verification_reference='https://example.org/terms')
               for _ in range(3)]
    old = job_factory(state='partial', entry_ids=[e.id for e in entries],
                      result_states=['succeeded','failed','interrupted'])
    entries[2].enabled = False
    db.commit()
    result = retry_job(db, old.id, now)
    assert result.job.trigger == 'retry'
    assert {r.entry_id for r in result.job.entries} == {entries[1].id}
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_jobs.py::test_retry_only_unsuccessful_eligible_entries -q`
- Expected: retry_job缺失或候选错误。

**Step 3: Write minimal implementation**
```python
def retry_job(db, job_id, now):
    """保留原结果，只对失败或中断且当前可用的入口新建任务。"""
    old = db.get(UpdateJob, job_id)
    if old is None:
        raise ApiError('job_not_found', '任务不存在', 404)
    active = db.scalar(select(UpdateJob).where(UpdateJob.state.in_(['pending', 'running'])))
    if active is not None:
        return EnqueueResult(active, True)
    allowed = {e.id for e in eligible_entries(db)}
    ids = [r.entry_id for r in old.entries
           if r.state in ('failed', 'interrupted') and r.entry_id in allowed]
    if not ids:
        raise ApiError('no_retryable_entries', '没有当前可重试的入口', 409)
    return enqueue(db, 'retry', ids, None, now)
```
- job.entries为I04显式relationship，级联仅删除结果不删除条目；不新增来源编辑能力。补测活跃任务复用、404优先、无候选、原成功结果/计数不变。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_jobs.py -q`
- Expected: PASS。自审手动retry与自动catchup候选不同，不把pending偷当失败。

**Step 5: Commit**
```bash
git add backend/app/application/jobs.py backend/tests/integration/persistence/test_jobs.py
git commit -m "feat: retry only unsuccessful approved entries"
```

- [x] **Task backend-025: 暴露任务创建、重试、当前与详情 JSON**

**Files:**
- Create: `backend/app/presentation/http/jobs.py`、`backend/tests/integration/api/test_jobs_api.py`
- Extend planned: `backend/app/application/jobs.py`、`backend/app/presentation/http/app.py`

**Reasoning:**
- D-024 页面重开后需要读取活动或最近任务；无记录应为null而不是404或伪造成功。

**Depends on:** backend-008, backend-024

**Interfaces:**
- Consumes: I08、I23、I24。
- Produces: I25 jobs_router/job_out/current_job，JobOut/EnqueueOut/CurrentJobOut。
- Contract checks: new202/reused200；current固定路由优先；计数由entry聚合，字段/枚举唯一。

**Step 1: Write the failing test**
```python
def test_job_routes_and_null_current(user_client, entry_factory):
    assert user_client.get('/api/update-jobs/current').json() == {'job': None}
    assert user_client.post('/api/update-jobs', json={'trigger': 'refresh'}).status_code == 409
    entry_factory(enabled=True, verification_status='allowed', verification_reason='测试许可',
                  verification_reference='https://example.org/terms')
    first = user_client.post('/api/update-jobs', json={'trigger': 'refresh'})
    assert first.status_code == 202 and first.json()['reused'] is False
    again = user_client.post('/api/update-jobs', json={'trigger': 'refresh'})
    assert again.status_code == 200 and again.json()['reused'] is True
    assert user_client.get('/api/update-jobs/current').json()['job']['id'] == first.json()['job']['id']
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/api/test_jobs_api.py::test_job_routes_and_null_current -q`
- Expected: 任务API尚未注册。

**Step 3: Write minimal implementation**
```python
@jobs_router.get('/api/update-jobs/current', name='job_current',
                  dependencies=[Depends(require_session)])
def job_current(db=Depends(get_db)):
    """活动优先，否则返回最近任务；从未更新时明确为null。"""
    return {'job': current_job(db)}

@jobs_router.post('/api/update-jobs', name='job_create',
                   dependencies=[Depends(require_write)])
def job_create(body: RefreshIn, db=Depends(get_db)):
    result = enqueue_refresh(db, datetime.now(UTC))
    return JSONResponse({'job': job_out(db, result.job).model_dump(mode='json'),
                         'reused': result.reused}, status_code=200 if result.reused else 202)
```
- RefreshIn仅Literal['refresh']；注册retry/detail，使用相同status/DTO。current按活动再created_at/id倒序；每入口许可与访问错误不混同。补测401/403、非法trigger400、404、partial/failed/interrupted DTO与无新增计数0。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/api/test_jobs_api.py tests/integration/persistence/test_jobs.py -q`
- Expected: PASS。自审API没有调用fetch/worker，任务不会阻塞HTTP。

**Step 5: Commit**
```bash
git add backend/app/presentation/http/jobs.py backend/app/application/jobs.py backend/app/presentation/http/app.py backend/tests/integration/api/test_jobs_api.py
git commit -m "feat: expose recoverable update job contracts"
```

- [x] **Task backend-026: 原子认领任务并串行提交每入口结果**

**Files:**
- Create: `backend/app/runtime/worker.py`、`backend/tests/integration/runtime/test_worker.py`
- Extend planned: `backend/app/infrastructure/persistence/database.py`、`backend/app/application/jobs.py`、`backend/app/application/ingestion.py`、`backend/tests/conftest.py`

**Reasoning:**
- D-007、D-030 的后台进程必须与API解耦；成功入口的条目和结果同次提交，崩溃不能丢失已提交成功状态。

**Depends on:** backend-022, backend-025

**Interfaces:**
- Consumes: I22 ingest_entry(result_id=…)、I04、I18。
- Produces: I26 claim_next/process_job/finish_job/worker_loop/single_worker_lock/application_lease；T02 worker_lab。
- Contract checks: 一个worker锁、pending原子claim、依序逐入口；成功/失败/混合终态与计数正确。

**Step 1: Write the failing test**
```python
from app.runtime.worker import claim_next, process_job

def test_serial_claim_and_partial_results(worker_lab, now):
    job = worker_lab.pending_job(entries=2)
    worker_lab.succeed(0, title='A', url='https://example.org/a')
    worker_lab.fail(1, code='source_unavailable')
    claimed = claim_next(worker_lab.db, now)
    assert claimed.id == job.id
    assert claim_next(worker_lab.other_db, now) is None
    process_job(worker_lab.db, claimed, worker_lab.client_factory, worker_lab.now)
    worker_lab.db.refresh(job)
    assert job.state == 'partial'
    assert [r.state for r in job.entries] == ['succeeded', 'failed']
    assert job.entries[0].count_added == 1
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/runtime/test_worker.py::test_serial_claim_and_partial_results -q`
- Expected: 独立worker接口尚不存在。

**Step 3: Write minimal implementation**
```python
def claim_next(db, now):
    """条件更新确保一个pending只认领一次，认领后立即提交释放写锁。"""
    candidate = select(UpdateJob.id).where(UpdateJob.state == 'pending').order_by(UpdateJob.id).limit(1)
    row = db.execute(update(UpdateJob).where(UpdateJob.id == candidate.scalar_subquery(),
        UpdateJob.state == 'pending').values(state='running', started_at=now)
        .returning(UpdateJob.id)).scalar_one_or_none()
    db.commit()
    return db.get(UpdateJob, row) if row is not None else None
```
- process_job逐入口将结果running短提交，之后在无写锁状态fetch。I22增加可选result_id，与条目/last_success在同事务写succeeded、计数与finished_at；任何入口错误rollback后另短事务写failed和safe_error。finish_job按成功数/失败数算succeeded/partial/failed并填结束时间；正常零条成功仍succeeded。worker启动先取得Linux flock单例锁、持有共享application_lease再处理，不创建API内线程。不同入口clients只来自固定配置。
- **Windows 开发修订**：本机分支用标准库 `msvcrt.locking` 对同一锁文件做真实互斥测试，生产分支仍为 `fcntl.flock`；这里只完成代码与跨平台锁语义，不声称 Linux 分支已运行。Linux `flock` 必须在 backend-038 镜像和 backend-042 真实进程演练重跑，未通过则后端发布结论保持阻塞。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/runtime/test_worker.py tests/integration/persistence/test_ingest.py -q`
- Expected: PASS；补测全失败/全部零条/一个worker拒绝第二实例与两连接claim。自审网络期间无SQLite写锁，注释说明同入口结果原子边界。

**Step 5: Commit**
```bash
git add backend/app/runtime/worker.py backend/app/infrastructure/persistence/database.py backend/app/application/jobs.py backend/app/application/ingestion.py backend/tests/integration/runtime/test_worker.py backend/tests/conftest.py
git commit -m "feat: process persistent source jobs serially"
```

- [x] **Task backend-027: 重启先结算旧 running 并保留 pending 队列**

**Files:**
- Extend planned: `backend/app/runtime/worker.py`、`backend/tests/integration/runtime/test_worker.py`

**Reasoning:**
- D-034 要先释放活动占用，否则当天补跑永远被旧running挡住；不能把正常pending也标中断。

**Depends on:** backend-026

**Interfaces:**
- Consumes: I26 单worker锁、I04。
- Produces: I27 settle_interrupted；startup在拿锁后、检查日程前调用。
- Contract checks: task结束时间、成功/失败结果不变；仅未完成结果interrupted；条目收藏保留。

**Step 1: Write the failing test**
```python
from app.runtime.worker import settle_interrupted

def test_restart_settles_running_not_pending(db, job_factory, now):
    old = job_factory(state='running', result_states=['succeeded', 'running', 'pending'])
    assert settle_interrupted(db, now) == 1
    db.refresh(old)
    assert old.state == 'interrupted' and old.finished_at == now
    assert [r.state for r in old.entries] == ['succeeded', 'interrupted', 'interrupted']
    queued = job_factory(state='pending')
    assert settle_interrupted(db, now) == 0
    db.refresh(queued)
    assert queued.state == 'pending'
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/runtime/test_worker.py::test_restart_settles_running_not_pending -q`
- Expected: 结算函数缺失。

**Step 3: Write minimal implementation**
```python
def settle_interrupted(db, now):
    """只在已取得独占worker运行锁的启动阶段结算前任进程。"""
    jobs = db.scalars(select(UpdateJob).where(UpdateJob.state == 'running')).all()
    for job in jobs:
        for result in job.entries:
            if result.state in ('pending', 'running'):
                result.state, result.finished_at = 'interrupted', now
                result.error = '上次更新进程中断'
        job.state, job.finished_at = 'interrupted', now
    db.commit()  # 先释放活动部分唯一索引，之后才可补跑。
    return len(jobs)
```
- worker启动次序固定：单例锁→application lease→settle→处理既有pending→日程检查。补测多次启动、原failed不改、成功计数不改与新的手动任务可入队；kill前已提交条目和书签用第二连接验证仍在。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/runtime/test_worker.py -q`
- Expected: PASS。自审不以进程内标记代替持久终态，不无条件取消pending。

**Step 5: Commit**
```bash
git add backend/app/runtime/worker.py backend/tests/integration/runtime/test_worker.py
git commit -m "feat: settle interrupted jobs before recovery"
```
