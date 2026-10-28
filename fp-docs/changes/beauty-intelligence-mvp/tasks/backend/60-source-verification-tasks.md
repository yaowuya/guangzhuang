## 五站逐入口核验任务

本组只规定未来执行时如何取得真实证据，不表示今天已联网或取得许可。每个站点结论可以是 pending 或 restricted，并保持禁用；唯有明确allowed且目标服务器probe成功才启用。至少一个入口真实通过的硬门禁另归 backend-041。

- [ ] **Task backend-033: 分别核验 PR TIMES RSS 与 Beauty 列表并接通核验 CLI**

**Files:**
- Create: `backend/verification/prtimes.json`、`backend/tests/test_verification.py`
- Extend planned: `backend/app/sources.py`、`backend/config/sources.json`、`backend/tests/conftest.py`

**Reasoning:**
- D-013、D-035 要求同站两个入口独立证据；RSS多行业窗口不能当作美妆全量流，许可也不能互相继承。

**Depends on:** backend-022, backend-029

**Interfaces:**
- Consumes: I15/I16/I18/I19/I20/I22。
- Produces: I33 verify_entry(db,spec,evidence,now)与 `python -m app.sources verify` CLI；T03 verification_files；PR TIMES SiteEvidence。
- Contract checks: 两入口分别有状态/原因/依据/probe；RSS与Beauty同原文只建一条；未确认条款不访问采集入口。

**Step 1: Write the failing test**
```python
def test_prtimes(verification_files):
    report = verification_files('prtimes')
    entries = {e['entry_key']: e for e in report['entries']}
    assert set(entries) == {'prtimes-rss', 'prtimes-beauty'}
    for e in entries.values():
        assert e['verification_reason'] and e['verification_reference']
        if e['verification_status'] == 'allowed':
            assert e['automation_allowed'] is True and e['title_storage_allowed'] is True
        else:
            assert e['probe']['attempted'] is False
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_prtimes -q`
- Expected: 真实证据文件缺失，不允许fixture伪造或skip补绿。

**Step 3: Write minimal implementation**
```python
def verify_entry(db, spec, evidence, now):
    """先审使用条件，再按受控请求验证元信息，不把访问成功视为许可。"""
    if evidence['verification_status'] != 'allowed':
        probe = {'attempted': False, 'succeeded': False, 'checked_at': None,
                 'title_count': 0, 'final_url': None, 'error': '许可未明确允许'}
    else:
        fetched = SafeClient.from_spec(spec).fetch(spec.url)
        batch = parse_rss(fetched.body, spec) if spec.kind == 'rss' else parse_list(fetched.body, spec)
        probe = {'attempted': True, 'succeeded': bool(batch.headlines),
                 'checked_at': now.isoformat(), 'title_count': len(batch.headlines),
                 'final_url': fetched.final_url, 'error': None if batch.headlines else '未取得有效标题'}
    apply_verification(db, evidence, probe, now)
    return dict(evidence, probe=probe)
```
- 执行前由用户提供目标环境与许可检查授权；逐项查 https://prtimes.jp/main/html/kiyaku ，只记结论和依据引用。不把本计划日期当reviewed_at。Beauty在实际页面确认container/item/title/link/date选择器、顺序与使用条件；没有依据就pending禁用。CLI只允许固定key，读取SiteEvidence对应行，调用verify_entry后原子写回；异常safe_error并保持禁用。用RSS与Beauty本地元信息样本验证同URL去重；不保存真实正文。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_prtimes tests/test_upsert.py -q`
- 未来获许可后才运行：`cd backend && python -m app.sources verify --entry prtimes-rss --evidence verification/prtimes.json --probe`；Beauty单独以prtimes-beauty运行。
- Expected: 证据结构/禁用规则PASS；只有目标环境真实probe的对应入口可enabled。自审两入口依据独立，RSS未分类可含非美妆标题。

**Step 5: Commit**
```bash
git add backend/app/sources.py backend/config/sources.json backend/verification/prtimes.json backend/tests/test_verification.py backend/tests/conftest.py
git commit -m "feat: verify prtimes entries with separate evidence"
```

- [ ] **Task backend-034: 核验 HAPPI RSS 的许可与目标服务器访问**

**Files:**
- Create: `backend/verification/happi.json`
- Extend planned: `backend/config/sources.json`、`backend/tests/test_verification.py`

**Reasoning:**
- 设计已记录普通请求403与RSS内文模块，不能从一次工具成功推断云端可用或扩张到正文采集。

**Depends on:** backend-033

**Interfaces:**
- Consumes: I33 verify_entry、I19 RSS白名单。
- Produces: I34 HAPPI SiteEvidence；不新增provider或HTTP接口。
- Contract checks: 仅happi-rss；403不绕过、不伪造成功；图片许可单独判断。

**Step 1: Write the failing test**
```python
def test_happi(verification_files):
    e = verification_files('happi')['entries'][0]
    assert e['entry_key'] == 'happi-rss'
    assert e['verification_reason'] and e['verification_reference']
    if e['probe']['succeeded']:
        assert e['verification_status'] == 'allowed' and e['probe']['title_count'] > 0
    if e['probe']['error']:
        assert 'CONTENT_SENTINEL' not in e['probe']['error']
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_happi -q`
- Expected: HAPPI独立目标环境证据缺失。

**Step 3: Write minimal implementation**
```python
report = read_evidence('verification/happi.json')
for row in report['entries']:
    assert row['entry_key'] == 'happi-rss'
    assert row['url'] == 'https://www.happi.com/feed/'
    if row['verification_status'] == 'allowed':
        assert row['automation_allowed'] and row['title_storage_allowed']
write_evidence('verification/happi.json', report)
```
- 先检查 https://www.happi.com/terms-conditions/ 的自动读取、标题存储与图片外链范围，真实记录SiteEvidence。明确许可后才用CLI在目标服务器probe；403/限制保留last_error，不换身份、不绕过防护、不采正文。无法确认则pending/restricted禁用，依旧完成准确核验记录；RSS含内文测试沿I19哨兵夹具验证。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_happi tests/test_parsers.py::test_rss_metadata_only -q`
- 未来获许可后运行：`cd backend && python -m app.sources verify --entry happi-rss --evidence verification/happi.json --probe`
- Expected: 结构测试PASS不等同真实入口成功；启用仅来自当次真实probe。自审403不改写许可结论。

**Step 5: Commit**
```bash
git add backend/config/sources.json backend/verification/happi.json backend/tests/test_verification.py
git commit -m "feat: record happi permission and server probe outcome"
```

- [ ] **Task backend-035: 核验青眼入口是否为可持续资讯流**

**Files:**
- Create: `backend/verification/qingyan.json`
- Extend planned: `backend/config/sources.json`、`backend/tests/test_verification.py`

**Reasoning:**
- 已看到的首页是热度排行，不能把热榜包装为已验证的最新资讯流。核验失败应诚实保持未启用。

**Depends on:** backend-033

**Interfaces:**
- Consumes: I33、I20 ListSelection。
- Produces: I35 青眼SiteEvidence与经验证选择器（仅确有证据时写入）。
- Contract checks: 许可/标题存储/持续入口/日期均分别确认；不从文章详情补元信息。

**Step 1: Write the failing test**
```python
def test_qingyan(verification_files):
    e = verification_files('qingyan')['entries'][0]
    assert e['entry_key'] == 'qingyan-list'
    assert e['verification_reason'] and e['verification_reference']
    if e['verification_status'] == 'allowed' and e['probe']['succeeded']:
        assert e['selection']['container'] and e['selection']['title'] and e['selection']['link']
        assert e['automation_allowed'] is True
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_qingyan -q`
- Expected: 青眼当前入口与使用条件证据缺失。

**Step 3: Write minimal implementation**
```python
report = read_evidence('verification/qingyan.json')
e = report['entries'][0]
if e['verification_status'] == 'allowed':
    selection = ListSelection(**e['selection'])
    assert selection.container and selection.item and selection.title and selection.link
else:
    e['probe']['attempted'] = False
    e['probe']['succeeded'] = False
write_evidence('verification/qingyan.json', report)
```
- 在授权环境检查 https://www.iqingyan.cn/ 的栏目/更新排序、自动读取与标题保存依据；只见热榜或条件不明则pending禁用并说明原因。若无可持续可用入口，不创建假资讯或从历史原型导入。发现需更换固定入口URL而当前证据不足时先回到来源核验，不自动跟随任意站外链接；批准并验证后静态更新候选，不能开放用户输入URL。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_qingyan tests/test_parsers.py::test_public_list_has_no_detail_fetch -q`
- 未来许可明确且入口确认后运行：`cd backend && python -m app.sources verify --entry qingyan-list --evidence verification/qingyan.json --probe`
- Expected: 真结论与禁用规则PASS；不以本地夹具证明青眼已接入。自审不会把热榜覆盖当作每日全量。

**Step 5: Commit**
```bash
git add backend/config/sources.json backend/verification/qingyan.json backend/tests/test_verification.py
git commit -m "feat: document verified qingyan entry limitations"
```

- [ ] **Task backend-036: 保持 PBN 建库限制并要求明确用途许可**

**Files:**
- Create: `backend/verification/pbn.json`
- Extend planned: `backend/config/sources.json`、`backend/tests/test_verification.py`

**Reasoning:**
- 设计明确PBN法律声明限制建库；可访问不等于可把标题存入数据库。

**Depends on:** backend-033

**Interfaces:**
- Consumes: I16、I33。
- Produces: I36 PBN SiteEvidence。
- Contract checks: 没有适用于本用途的明确许可则pending/restricted且禁用，不probe采集入口。

**Step 1: Write the failing test**
```python
def test_pbn(verification_files):
    e = verification_files('pbn')['entries'][0]
    assert e['entry_key'] == 'pbn-list'
    assert e['verification_reference']
    allowed = e['automation_allowed'] is True and e['title_storage_allowed'] is True
    if not allowed:
        assert e['verification_status'] != 'allowed'
        assert e['probe']['attempted'] is False
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_pbn -q`
- Expected: PBN限制与许可依据未记录。

**Step 3: Write minimal implementation**
```python
report = read_evidence('verification/pbn.json')
e = report['entries'][0]
if not (e['automation_allowed'] is True and e['title_storage_allowed'] is True):
    assert e['verification_status'] in {'pending', 'restricted'}
    e['probe'] = {'attempted': False, 'succeeded': False, 'checked_at': None,
                  'title_count': 0, 'final_url': None, 'error': '尚无适用于标题建库的明确许可'}
write_evidence('verification/pbn.json', report)
```
- 复核 https://www.premiumbeautynews.com/en/legal-notice,85 ，记录使用条件日期与依据引用；只有用户提供或可验证的明确用途许可才改allowed，且图片另核验。未获许可不从/en/列表采集、不改用镜像。需要人工向权利方确认时把该入口保持禁用，不阻塞其它已允许站点交付。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_pbn -q`
- 有明确许可后才运行：`cd backend && python -m app.sources verify --entry pbn-list --evidence verification/pbn.json --probe`
- Expected: 禁用/证据一致性PASS；没有许可绝不宣称PBN可用。自审不得以外链或个人用途自动推导豁免。

**Step 5: Commit**
```bash
git add backend/config/sources.json backend/verification/pbn.json backend/tests/test_verification.py
git commit -m "feat: enforce pbn database permission gate"
```

- [ ] **Task backend-037: 核验 COSIN 标题保存及图片条件而不猜测 RSS 地址**

**Files:**
- Create: `backend/verification/cosin.json`
- Extend planned: `backend/config/sources.json`、`backend/tests/test_verification.py`

**Reasoning:**
- 设计只看到首页标题与RSS入口线索，未验证运行；页脚禁止复制分发不能被忽略。

**Depends on:** backend-033

**Interfaces:**
- Consumes: I16、I20、I33。
- Produces: I37 COSIN SiteEvidence。
- Contract checks: URL/选择器来自实际核验；不以一个RSS图标假定可运行；图片条件与标题许可分离。

**Step 1: Write the failing test**
```python
def test_cosin(verification_files):
    e = verification_files('cosin')['entries'][0]
    assert e['entry_key'] == 'cosin-list'
    assert e['verification_reason'] and e['verification_reference']
    if e['image_allowed']:
        assert e['image_hosts']
    if e['probe']['succeeded']:
        assert e['verification_status'] == 'allowed' and e['probe']['title_count'] > 0
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_cosin -q`
- Expected: COSIN独立运行/许可证据缺失。

**Step 3: Write minimal implementation**
```python
report = read_evidence('verification/cosin.json')
e = report['entries'][0]
assert e['url'].startswith('https://cosinkorea.com/')
if not e['image_allowed']:
    e['image_hosts'] = []
if e['verification_status'] != 'allowed':
    e['probe']['attempted'] = False
    e['probe']['succeeded'] = False
write_evidence('verification/cosin.json', report)
```
- 在 https://cosinkorea.com/ 核实实际入口和自动读取/标题存储使用条件；页脚限制与授权依据均保留引用。允许时验证公开列表选择器；发现真实RSS可作为来源核验输入，但未明确批准并更新固定配置前不启用新入口。日期无法取得则NULL，不从URL/采集时间猜。图片无明确许可一律不存。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_verification.py::test_cosin -q`
- 未来许可明确后运行：`cd backend && python -m app.sources verify --entry cosin-list --evidence verification/cosin.json --probe`
- Expected: 诚实记录PASS，真实来源可用仍由backend-041验收。自审五站记录各自环境与检查时间，不复制许可结论。

**Step 5: Commit**
```bash
git add backend/config/sources.json backend/verification/cosin.json backend/tests/test_verification.py
git commit -m "feat: verify cosin metadata and image permission boundaries"
```
