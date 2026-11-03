## 真实环境验收与后端发布门禁

本组执行前必须有用户明确授权、目标云环境、可用HTTPS域名、私密凭据与来源条件。所有证据由真实操作生成；默认离线pytest不运行本组，也不能把未运行或skip算作通过。发现缺少这些前提时报告具体条件并保留任务未勾选。

- [ ] **Task backend-041: 验收目标 HTTPS 与至少一个真实许可来源更新**

**Files:**
- Create: `backend/tests/acceptance/__init__.py`、`backend/tests/acceptance/test_live.py`、`backend/verification/live-source.json`
- Extend planned: `backend/tests/conftest.py`、`backend/pyproject.toml`、`deploy/README.md`

**Reasoning:**
- D-028 的正式交付不接受全模拟、空库假成功或五站列表冒充真实接入。

**Depends on:** backend-040

**Interfaces:**
- Consumes: I33–I40、I25任务HTTP、I12阅读HTTP。
- Produces: I41 capture_live_source、T03 live_env与LiveEvidence。
- Contract checks: 真TLS校验、同域页面/API、至少一个allowed且enabled入口、真实title/link入库、会话/收藏重开持久。

**Step 1: Write the failing test**
```python
from pathlib import Path
import json

def test_live_source(live_env):
    report = capture_live_source(live_env)
    Path('verification/live-source.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    assert report['passed'] is True
    assert all(c['passed'] for c in report['checks'])
    assert {'https', 'entry_permission', 'real_title', 'bookmark_persistence'} <= {
        c['name'] for c in report['checks']}
```
**Step 2: Run test to verify it fails**
- Run（仅未来用户授权的目标环境）：`cd backend && python -m pytest tests/acceptance/test_live.py::test_live_source --live -q`
- Expected: 初始无真实来源/HTTPS或证据时断言失败；缺真实凭据则明确UsageError，不能skip后宣称已通过。

**Step 3: Write minimal implementation**
```python
def capture_live_source(env):
    """只记录实际HTTPS调用结果，不关闭证书校验或注入模拟资讯。"""
    with httpx.Client(base_url=env.origin, verify=True, follow_redirects=False) as client:
        login = client.post('/api/auth/login', json={'password': env.password},
                            headers={'Origin': env.origin})
        login.raise_for_status()
        client.headers.update({'Origin': env.origin, 'X-CSRF-Token': login.json()['csrf_token']})
        sources = client.get('/api/sources').json()['items']
        allowed = [e for s in sources for e in s['entries']
                   if e['enabled'] and e['verification_status'] == 'allowed']
        assert allowed, '没有获许可且真实可用的入口，不能交付'
        created = client.post('/api/update-jobs', json={'trigger': 'refresh'})
        assert created.status_code in (200, 202)
```
- helper在600秒有界轮询内取得终态，核对成功入口与数据库来源身份，GET真实标题/原文URL，无正文；许可依据与核验环境匹配。收藏某真实条目、退出重新登录验证持久，恢复原收藏状态。取得页面响应而非旧原型；不调用浏览器图片下载/代理服务。报告仅保存request_id、job ID、状态、时间、计数和依据引用；原文链接可记，私密信息不可记。真实内容不足或来源全部失败必须FAIL。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/acceptance/test_live.py::test_live_source --live -q`
- Expected: 授权真实环境PASS且证据可复查，不以本计划或离线夹具代替。自审来源条款仍适用、图无许可则NULL并不阻断标题。

**Step 5: Commit**
```bash
git add backend/tests/acceptance/__init__.py backend/tests/acceptance/test_live.py backend/tests/conftest.py backend/pyproject.toml backend/verification/live-source.json deploy/README.md
git commit -m "test: verify real permitted source over production https"
```

- [ ] **Task backend-042: 记录真实 07:30 日程与受控中断恢复演练**

**Files:**
- Create: `backend/verification/live-schedule.json`
- Extend planned: `backend/tests/acceptance/test_live.py`、`deploy/README.md`

**Reasoning:**
- D-016、D-030、D-033、D-034 的跨重启规则不能只依靠fake clock单测证明生产配置正确。

**Depends on:** backend-041

**Interfaces:**
- Consumes: I27–I29、I25、I41 live_env。
- Produces: I42 capture_schedule 与LiveEvidence。
- Contract checks: 北京时间07:30的真实任务；缺当天记录晚恢复仅catchup一次；中断成功保留、pending保留；反复重启不增加次数。

**Step 1: Write the failing test**
```python
import json
from pathlib import Path

def test_live_schedule(live_env):
    report = capture_schedule(live_env)
    Path('verification/live-schedule.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    required = {'actual_0730', 'missing_schedule_catchup', 'interrupted_settlement',
                'single_catchup_after_restarts', 'pending_preserved'}
    assert required <= {c['name'] for c in report['checks'] if c['passed']}
    assert report['passed'] is True
```
**Step 2: Run test to verify it fails**
- Run（未来真实观测后）：`cd backend && python -m pytest tests/acceptance/test_live.py::test_live_schedule --live -q`
- Expected: 尚无真实07:30或恢复证据时FAIL；不得补写假时间或将模拟测试改名为实际观测。

**Step 3: Write minimal implementation**
```python
def capture_schedule(env):
    """核对用户批准的维护演练记录与任务API，不修改服务器系统时钟。"""
    report = read_evidence(env.schedule_observation)
    assert report['origin'] == env.origin and report['environment'] == env.environment
    names = {c['name'] for c in report['checks'] if c['passed']}
    required = {'actual_0730', 'missing_schedule_catchup', 'interrupted_settlement',
                'single_catchup_after_restarts', 'pending_preserved'}
    report['passed'] = required <= names
    return report
```
- 在用户批准的维护窗口真实观察一次北京时间07:30任务，保存schedule_date/created_at/trigger/结果。缺记录/中断/重复重启演练可在同主机隔离的数据库副本进行，真实进程与生产同镜像，不启第二公网服务；标明隔离环境，不能冒充实际07:30证据。需要停止/kill生产worker时必须另获明确维护授权且先备份，不自动重置生产库或篡改时间。演练验证旧running先interrupted释放索引、成功标题/收藏保留、仅未成功入口补跑、第二次重启无新catchup、昨日不回放；pending案例独立运行。helper读取的原始观察记录也须来自实际API/数据库查询，附可复查task ID与UTC/北京时间，不靠手填passed布尔值，逐项重新计算。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/acceptance/test_live.py::test_live_schedule --live -q`
- Expected: 真实07:30与隔离进程演练证据均完整才PASS；等不到该时间则保留未完成。自审不把一次catchup当正常定时的证据。

**Step 5: Commit**
```bash
git add backend/verification/live-schedule.json backend/tests/acceptance/test_live.py deploy/README.md
git commit -m "test: record scheduled and interrupted update recovery evidence"
```

- [ ] **Task backend-043: 在独立恢复副本验证七份备份与回滚可读性**

**Files:**
- Create: `backend/verification/live-restore.json`
- Extend planned: `backend/tests/acceptance/test_live.py`、`deploy/README.md`

**Reasoning:**
- D-019 的目标服务器磁盘/权限/文件卷可能与单测不同，必须从实际备份恢复，而不覆盖唯一生产库演练。

**Depends on:** backend-041

**Interfaces:**
- Consumes: I31、I32、I39。
- Produces: I43 capture_restore 和LiveEvidence。
- Contract checks: 实际卷上有效快照、最多七日备份、独立还原schema/条目/收藏/入口状态/任务一致，损失窗口明确。

**Step 1: Write the failing test**
```python
import json
from pathlib import Path

def test_live_restore(live_env):
    report = capture_restore(live_env)
    Path('verification/live-restore.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    assert report['passed'] is True
    assert {'integrity', 'seven_retained', 'isolated_restore', 'bookmark_readable',
            'loss_window_confirmed'} <= {c['name'] for c in report['checks'] if c['passed']}
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/acceptance/test_live.py::test_live_restore --live -q`
- Expected: 目标卷实际恢复证据缺失时FAIL，不能拿文件名存在当恢复通过。

**Step 3: Write minimal implementation**
```python
def capture_restore(env):
    """对真实备份的隔离副本检查，绝不默认覆盖生产数据库。"""
    report = read_evidence(env.restore_observation)
    with sqlite3.connect(f'file:{env.restored_copy}?mode=ro', uri=True) as db:
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        bookmarks = db.execute('SELECT COUNT(*) FROM bookmarks b JOIN articles a ON a.id=b.article_id').fetchone()[0]
    assert integrity
    report['passed'] = integrity and all(c['passed'] for c in report['checks'])
    return report
```
- 先由授权操作者生成真实在线备份并在隔离路径恢复，使用独立lease、不碰生产库。验证备份日期与最近七份轮换（可用同机隔离目录受控日期样本验证七份策略，清楚标记演练），恢复后核对实际库计数与选定收藏、七表迁移版本、入口许可/任务；损失窗口与本机故障不覆盖边界由用户确认。报告校验不能仅信任上一步passed输入，每项保存并重算实测值；保留安全副本直到核验结束。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/acceptance/test_live.py::test_live_restore --live -q`
- Expected: 实际目标卷恢复PASS；生产库没有为演练被自动覆盖。自审同机备份不被报告为异地灾备。

**Step 5: Commit**
```bash
git add backend/verification/live-restore.json backend/tests/acceptance/test_live.py deploy/README.md
git commit -m "test: exercise isolated restore from real sqlite backup"
```

- [ ] **Task backend-044: 验证真实错误可见、凭据脱敏和无超范围存储**

**Files:**
- Create: `backend/verification/live-audit.json`
- Extend planned: `backend/tests/acceptance/test_live.py`、`deploy/README.md`

**Reasoning:**
- D-008、D-026 的安全要求覆盖数据库、日志与部署，不是界面没有正文就足够。

**Depends on:** backend-041

**Interfaces:**
- Consumes: I18、I30、I40及真实部署日志。
- Produces: I44 capture_audit 和LiveEvidence。
- Contract checks: 未许可不访问，SSRF/超限拒绝、锁/磁盘/备份错误可见；无正文/摘要/图片字节或凭据落库/日志。

**Step 1: Write the failing test**
```python
import json
from pathlib import Path

def test_live_audit(live_env):
    report = capture_audit(live_env)
    Path('verification/live-audit.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    required = {'no_body_storage', 'no_image_proxy', 'secret_redaction',
                'egress_blocking', 'storage_failure_visible', 'backup_failure_visible'}
    assert required <= {c['name'] for c in report['checks'] if c['passed']}
    assert report['passed'] is True
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/acceptance/test_live.py::test_live_audit --live -q`
- Expected: 审计实测证据缺失时FAIL，不将未检查标记为通过。

**Step 3: Write minimal implementation**
```python
def capture_audit(env):
    """审计只保存结论和可复查标识，不再次泄露被检查的敏感内容。"""
    report = read_evidence(env.audit_observation)
    tables = env.readonly_db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall()
    columns = '\n'.join(sql or '' for _, sql in tables).casefold()
    assert all(word not in columns for word in ('body_blob', 'summary_text', 'image_bytes'))
    report['passed'] = all(c['passed'] for c in report['checks'])
    return report
```
- 实际schema与抽样记录仅允许设计字段；进一步扫描非列名的body/summary残留、原始响应与日志哨兵，不只依靠三个列名。以隔离测试数据注入异常/假Cookie值并检查Caddy/API/worker日志不含敏感值；不可打印真实凭据作为审计。锁满盘/备份失败在隔离卷演练，显示安全错误且旧内容可读，不实际填满生产磁盘。Caddy无图片代理路由，worker出站审计只有已批准元信息入口；浏览器图片失败验收由前端owner负责，本任务仅核实后端无下载/代理。每个check从实际查询/日志片段的脱敏摘要重算，不相信输入布尔值。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/acceptance/test_live.py::test_live_audit --live -q`
- Expected: 全项实测PASS。自审不把错误掩盖成空列表、更新成功或新last_success时间。

**Step 5: Commit**
```bash
git add backend/verification/live-audit.json backend/tests/acceptance/test_live.py deploy/README.md
git commit -m "test: audit live safety storage and observable failures"
```

- [ ] **Task backend-045: 汇总真实证据并建立不可跳过的后端发布结论**

**Files:**
- Create: `backend/tests/acceptance/test_release.py`、`backend/verification/release.json`
- Extend planned: `deploy/README.md`

**Reasoning:**
- P-013/D-028 的交付门槛必须同时覆盖自动测试与目标环境，缺许可、云资源或演练不能靠文档完备宣布完成。

**Depends on:** backend-042, backend-043, backend-044

**Interfaces:**
- Consumes: I41–I44四份真实LiveEvidence、全部离线测试结果。
- Produces: I45 release_report(paths)与最终后端发布报告，不产生前端task ID或执行文件。
- Contract checks: 同一目标环境/域名、真实非空来源、实际07:30、恢复/安全全部通过；无skip冒充通过。

**Step 1: Write the failing test**
```python
from pathlib import Path
import json

def test_backend_release(live_env):
    paths = [Path('verification') / f'live-{name}.json'
             for name in ('source', 'schedule', 'restore', 'audit')]
    report = release_report(paths)
    assert report['passed'] is True
    assert report['origin'] == live_env.origin
    Path('verification/release.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/acceptance/test_release.py::test_backend_release --live -q`
- Expected: 任一真实证据缺失、失败、环境不一致或尚未执行时FAIL；不得空列表all()假通过。

**Step 3: Write minimal implementation**
```python
def release_report(paths):
    """仅合并完整且可复查的真实证据，不把计划/skip当成执行成功。"""
    reports = [read_evidence(p) for p in paths]
    assert len(reports) == 4 and all(r['checks'] for r in reports)
    assert len({r['origin'] for r in reports}) == 1
    assert len({r['environment'] for r in reports}) == 1
    assert all(r['passed'] and all(c['passed'] for c in r['checks']) for r in reports)
    return {'checked_at': datetime.now(UTC).isoformat(), 'origin': reports[0]['origin'],
            'environment': reports[0]['environment'], 'passed': True,
            'checks': [c for r in reports for c in r['checks']]}
```
- README保留实际依赖/构建/迁移版本、真实来源限制、备份与回滚损失窗口、错误查看和维护命令。核对proposal/backend design原文件未因实现擅改；上游small XOR与本端split manifest有效。若真实来源全部未获许可，报告具体未满足条件，任务保持未勾选，不削减为演示版；前端整体验收由主调度另行确认，不在此声称完成。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests --ignore=tests/acceptance -q`；`cd backend && python -m pytest tests/acceptance --live -q`；`sh deploy/compose.sh deploy/.env docker-compose.yml config --quiet`
- Expected: 离线与真实环境均PASS，报告可复查且无凭据。工程质量自审公共职责、事务/许可/DNS原因注释与简化边界，不满足则先修再提交。

**Step 5: Commit**
```bash
git add backend/tests/acceptance/test_release.py backend/verification/release.json deploy/README.md
git commit -m "test: gate backend release on verified live evidence"
```
