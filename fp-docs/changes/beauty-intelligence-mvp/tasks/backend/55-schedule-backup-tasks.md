## 日程恢复与数据保障任务

- [x] **Task backend-028: 按北京时间 07:30 创建当日日程且不阻塞手动任务**

**Files:**
- Create: `backend/app/schedule.py`、`backend/tests/test_schedule.py`
- Extend planned: `backend/app/worker.py`

**Reasoning:**
- P-005 与 D-016 共同限定北京时间每日一次，不得混用 UTC 日期或并行采集。

**Depends on:** backend-027

**Interfaces:**
- Consumes: I23 enqueue、I26/I27 worker生命周期。
- Produces: I28 schedule_due/tick。
- Contract checks: 07:30前不创建；日程date为Asia/Shanghai；活跃时不并行；同日schedule唯一。

**Step 1: Write the failing test**
```python
from datetime import datetime, UTC
from app.schedule import schedule_due

def test_beijing_0730_schedule(db, entry_factory):
    entry_factory(enabled=True, verification_status='allowed', verification_reason='测试许可',
                  verification_reference='https://example.org/terms')
    assert schedule_due(db, datetime(2026, 10, 26, 23, 29, 59, tzinfo=UTC)) is None
    result = schedule_due(db, datetime(2026, 10, 26, 23, 30, tzinfo=UTC))
    assert result.job.trigger == 'schedule'
    assert str(result.job.schedule_date) == '2026-10-27'
    assert schedule_due(db, datetime(2026, 10, 26, 23, 30, 1, tzinfo=UTC)) is None
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_schedule.py::test_beijing_0730_schedule -q`
- Expected: 日程模块不存在。

**Step 3: Write minimal implementation**
```python
def schedule_due(db, now):
    """常驻tick只在07:30分钟窗口创建正常日程，迟到由catchup负责。"""
    local = now.astimezone(ZoneInfo('Asia/Shanghai'))
    if (local.hour, local.minute) != (7, 30):
        return None
    existing = db.scalar(select(UpdateJob).where(UpdateJob.schedule_date == local.date(),
                         UpdateJob.trigger.in_(['schedule', 'catchup'])))
    active = db.scalar(select(UpdateJob).where(UpdateJob.state.in_(['pending', 'running'])))
    if existing is not None or active is not None:
        return None
    ids = [e.id for e in eligible_entries(db)]
    return enqueue(db, 'schedule', ids, local.date(), now) if ids else None
```
- worker每秒空闲tick，启动先settle并执行catchup检查，不能把迟到启动伪造为准点schedule。常驻tick先schedule_due再catchup_due；活动任务结束再次检查。日期跨越、无入口、手动占用07:30均有测试。正常schedule与catchup是不同触发，运行次数仍受唯一索引限制。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_schedule.py::test_beijing_0730_schedule -q`
- Expected: PASS。自审没有系统本地时区依赖，不回放前一天。

**Step 5: Commit**
```bash
git add backend/app/schedule.py backend/app/worker.py backend/tests/test_schedule.py
git commit -m "feat: schedule daily updates at shanghai 0730"
```

- [x] **Task backend-029: 当天缺失或未成功日程只自动补跑一次**

**Files:**
- Extend planned: `backend/app/schedule.py`、`backend/app/worker.py`、`backend/tests/test_schedule.py`

**Reasoning:**
- D-016、D-030、D-033 区分“没当天记录”和“有部分结果”，catchup持久行本身就是次数证据。

**Depends on:** backend-028

**Interfaces:**
- Consumes: I23、I27、I28。
- Produces: I29 catchup_due，接入启动及常驻tick。
- Contract checks: 无记录全选当前eligible，有结果只补非成功；重复重启不增次数；禁用重校验，不追历史。

**Step 1: Write the failing test**
```python
from datetime import datetime, UTC
from app.schedule import catchup_due
from app.worker import settle_interrupted

def test_missing_partial_and_restarts(db, entry_factory):
    a = entry_factory(enabled=True, verification_status='allowed', verification_reason='测试许可',
                      verification_reference='https://example.org/terms')
    now = datetime(2026, 10, 27, 2, 0, tzinfo=UTC)
    result = catchup_due(db, now)
    assert result.job.trigger == 'catchup'
    assert [r.entry_id for r in result.job.entries] == [a.id]
    result.job.state, result.job.finished_at = 'interrupted', now
    db.commit()
    settle_interrupted(db, now)
    assert catchup_due(db, now) is None
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_schedule.py::test_missing_partial_and_restarts -q`
- Expected: 补跑逻辑缺失。

**Step 3: Write minimal implementation**
```python
def catchup_due(db, now):
    """当天最多一条catchup；缺日程与部分完成分别选择候选。"""
    local = now.astimezone(ZoneInfo('Asia/Shanghai'))
    if local.time().replace(tzinfo=None) < time(7, 30):
        return None
    used = db.scalar(select(UpdateJob.id).where(UpdateJob.trigger == 'catchup',
                     UpdateJob.schedule_date == local.date()))
    active = db.scalar(select(UpdateJob.id).where(UpdateJob.state.in_(['pending', 'running'])))
    if used is not None or active is not None:
        return None
    scheduled = db.scalar(select(UpdateJob).where(UpdateJob.trigger == 'schedule',
                           UpdateJob.schedule_date == local.date()))
    allowed = {e.id for e in eligible_entries(db)}
    if scheduled is not None and scheduled.state == 'succeeded':
        return None
    ids = allowed if scheduled is None or not scheduled.entries else {
        r.entry_id for r in scheduled.entries if r.state != 'succeeded'} & allowed
    return enqueue(db, 'catchup', sorted(ids), local.date(), now) if ids else None
```
- enqueue事务与catchup日期唯一约束共同消除竞争。补测无结果行、partial/failed/interrupted、成功不重复、禁用项剔除、活动手动完成后补跑、昨日失败不回放以及pending保留。执行前worker仍重新验证入口条件。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_schedule.py tests/test_worker.py -q`
- Expected: PASS。自审当天次数不存内存flag，耗尽后只允许手动retry或次日日程。

**Step 5: Commit**
```bash
git add backend/app/schedule.py backend/app/worker.py backend/tests/test_schedule.py
git commit -m "feat: persist bounded same day recovery updates"
```

- [x] **Task backend-030: 集成验证中断后成功保留与阅读不受采集阻塞**

**Files:**
- Create: `backend/tests/test_recovery_integration.py`
- Extend planned: `backend/app/worker.py`、`backend/app/ingest.py`、`backend/app/jobs.py`

**Reasoning:**
- 单函数测试不能证明两个连接、进程重启和部分成功在一起仍正确；本任务只修正直接暴露的边界，不另建服务。

**Depends on:** backend-014, backend-029

**Interfaces:**
- Consumes: I14、I22–I29、T02 worker_lab。
- Produces: I30 跨连接恢复证据，不产生新HTTP接口。
- Contract checks: 网络暂停时列表/详情/收藏可读；kill后旧running先终结，成功元信息和书签保留；锁/满盘不假报成功。

**Step 1: Write the failing test**
```python
from app.worker import settle_interrupted
from app.schedule import catchup_due

def test_reading_survives_interrupted_update(worker_lab, user_client, now, caplog):
    old_article = worker_lab.article(bookmarked=True)
    job = worker_lab.running_job(result_states=['succeeded', 'running'])
    old_id, unfinished = job.id, job.entries[1].entry_id
    worker_lab.pause_network()
    worker_lab.start_paused_job(old_id)
    r = user_client.get(f'/api/articles/{old_article.id}')
    assert r.status_code == 200 and r.json()['bookmarked'] is True
    worker_lab.crash_and_reopen()
    settle_interrupted(worker_lab.db, worker_lab.after_0730)
    recovered = catchup_due(worker_lab.db, worker_lab.after_0730)
    assert old_id != recovered.job.id
    assert {x.entry_id for x in recovered.job.entries} == {unfinished}
    assert any(r.message == 'job_interrupted' and r.job_id == old_id for r in caplog.records)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_recovery_integration.py::test_reading_survives_interrupted_update -q`
- Expected: FAIL，前序结算尚未产生可审计的job_interrupted安全事件；其余断言同时检查真实两连接/进程恢复边界。

**Step 3: Write minimal implementation**
```python
# worker启动中的固定次序；持有锁直到退出，网络不在SQLite写事务内。
with single_worker_lock(settings.data_dir / 'worker.lock'):
    with application_lease(settings.data_dir / 'application.lock'):
        with db_session(make_engine(settings.database_url)) as db:
            settle_interrupted(db, datetime.now(UTC))
            catchup_due(db, datetime.now(UTC))
# 在settle_interrupted提交成功后，对每个已结算ID发出无正文/凭据的事件。
logger.warning('job_interrupted', extra={'job_id': settled_job_id})
```
- settled_job_id来自本次结算已提交的job.id；安全事件不在事务失败时假报成功。worker_lab为真实临时SQLite、两个独立Session和可暂停transport，不模拟数据库结果。故障测试注入sqlite锁/commit失败，assert 503或failed及安全错误，不覆盖last_success/旧内容。必要修正只限这三个既定模块；app lease启动代码在I26 lifecycle中合并，不增加第二worker循环。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_recovery_integration.py tests/test_jobs.py tests/test_schedule.py -q`
- Expected: PASS。自审事务边界的注释反映真实提交，不把模拟网络算真实来源验收。

**Step 5: Commit**
```bash
git add backend/tests/test_recovery_integration.py backend/app/worker.py backend/app/ingest.py backend/app/jobs.py
git commit -m "test: verify durable recovery and uninterrupted reading"
```

- [x] **Task backend-031: 每日在线一致性备份并仅轮换最近七份**

**Files:**
- Create: `backend/app/backup.py`、`backend/tests/test_backup.py`
- Extend planned: `backend/app/worker.py`、`backend/app/schedule.py`

**Reasoning:**
- D-019 不能用直接拷贝运行数据库替代SQLite一致性备份，失败也不能先删除最后可用文件。

**Depends on:** backend-029

**Interfaces:**
- Consumes: I02 database path、I28 tick。
- Produces: I31 backup_once/daily_backup。
- Contract checks: 按北京时间日期命名；每天一个有效备份；integrity_check后原子rename再轮换；失败可见且旧份保留。

**Step 1: Write the failing test**
```python
import sqlite3
from datetime import timedelta
from app.backup import daily_backup

def test_consistent_backup_and_rotation(db, article_factory, tmp_path, now):
    article_factory()
    folder = tmp_path / 'backups'
    path = db.bind.url.database
    for day in range(9):
        daily_backup(path, folder, now + timedelta(days=day))
    files = sorted(folder.glob('backup-*.sqlite3'))
    assert len(files) == 7
    with sqlite3.connect(files[-1]) as restored:
        assert restored.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert restored.execute('SELECT COUNT(*) FROM articles').fetchone()[0] == 1
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_backup.py::test_consistent_backup_and_rotation -q`
- Expected: 备份函数缺失。

**Step 3: Write minimal implementation**
```python
def backup_once(db_path, directory, now):
    """生成通过完整性检查的在线快照，成功落盘后才删旧备份。"""
    directory.mkdir(parents=True, exist_ok=True)
    day = now.astimezone(ZoneInfo('Asia/Shanghai')).date()
    target = directory / f'backup-{day}.sqlite3'
    temporary = target.with_suffix('.tmp')
    with sqlite3.connect(db_path) as source, sqlite3.connect(temporary) as destination:
        source.backup(destination)
        if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ApiError('backup_failed', '备份完整性检查失败', 503)
    temporary.replace(target)
    for obsolete in sorted(directory.glob('backup-*.sqlite3'))[:-7]:
        obsolete.unlink()
    return target
```
- daily_backup先检查当日有效文件；tick每日首次空闲时执行，不与采集并行写，失败写安全日志并保留旧份，下个tick允许重试。仅对存在且具有七张业务表/迁移版本的数据库备份，路径错误或未迁移库拒绝成功；限制文件权限，tmp清理不删除有效备份。补测磁盘满/校验失败/已有当日/跨时区、原库持续可读；不把同机备份宣传为灾难恢复。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_backup.py::test_consistent_backup_and_rotation -q`
- Expected: PASS；失败路径保留七份内最后可用快照。自审备份使用API而非copy运行DB。

**Step 5: Commit**
```bash
git add backend/app/backup.py backend/app/worker.py backend/app/schedule.py backend/tests/test_backup.py
git commit -m "feat: rotate seven consistent daily sqlite backups"
```

- [x] **Task backend-032: 停写、确认损失窗口后离线恢复并记录回滚命令**

**Files:**
- Extend planned: `backend/app/backup.py`、`backend/app/database.py`、`backend/app/main.py`、`backend/app/worker.py`（共享 application lease）、`backend/tests/test_backup.py`
- Create: `deploy/README.md`

**Reasoning:**
- D-019、迁移/回滚要求不能只证明备份文件存在；覆盖运行库必须先明确告知备份后的写入将丢失。

**Depends on:** backend-030, backend-031

**Interfaces:**
- Consumes: I26 application_lease、I31。
- Produces: I32 restore_backup与CLI；API lifespan也持共享lease，恢复独占取得才可写。
- Contract checks: 无确认/仍运行/坏文件拒绝；恢复前保留当前库快照；恢复后条目/收藏/许可/任务可读。

**Step 1: Write the failing test**
```python
import pytest
from app.backup import backup_once, restore_backup
from app.database import application_lease

def test_restore_requires_stop_and_confirmation(db, tmp_path, now):
    image = backup_once(db.bind.url.database, tmp_path / 'backups', now)
    lease = tmp_path / 'application.lock'
    with pytest.raises(ValueError):
        restore_backup(image, db.bind.url.database, lease, '')
    with application_lease(lease):
        with pytest.raises(RuntimeError, match='仍在运行'):
            restore_backup(image, db.bind.url.database, lease, '已确认损失备份后的写入')
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_backup.py::test_restore_requires_stop_and_confirmation -q`
- Expected: 恢复函数缺失。

**Step 3: Write minimal implementation**
```python
def restore_backup(backup_path, db_path, lease_path, confirmation):
    """独占停写后恢复已验证快照；确认文本不能替代实际停服务。"""
    if not confirmation.strip():
        raise ValueError('必须确认备份后的写入会丢失')
    with application_lease(lease_path, exclusive=True):
        with sqlite3.connect(f'file:{backup_path}?mode=ro', uri=True) as source:
            if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('备份损坏')
            staged = Path(db_path).with_suffix('.restore')
            with sqlite3.connect(staged) as destination:
                source.backup(destination)
        staged.replace(db_path)
```
- 实际替换前使用I31一致性方法保留当前库为独立pre-restore安全副本；检查七表和alembic版本，数据库引擎关闭并释放连接后替换。README写明 `docker compose -f deploy/compose.yaml stop api worker`、独立恢复容器、`alembic upgrade head`与重启检查；这些命令依赖后续Compose创建，本任务离线测试不启动服务。严禁恢复后自动宣称成功，须重开库核验收藏/任务，API持lease防止误覆盖运行文件。
- **Windows 开发修订**：本任务先以实际 Windows 文件互斥、独立 SQLite 文件和原子替换完成代码测试；生产 Linux `flock` 跨 API/worker/恢复进程及 Compose 卷恢复必须在 backend-038/backend-043 重跑，当前 checkbox 不代表目标 Linux 恢复演练已通过。

**Step 4: Run test to verify it passes**
- Run（Linux目标运行环境）：`cd backend && python -m pytest tests/test_backup.py -q`
- Expected: PASS；增加真实临时库还原往返、坏文件拒绝和前置副本断言。自审锁跨API/worker两进程有效，回滚损失窗口说明准确。

**Step 5: Commit**
```bash
git add backend/app/backup.py backend/app/database.py backend/app/main.py backend/tests/test_backup.py deploy/README.md
git commit -m "feat: restore sqlite only after exclusive stop and confirmation"
```
