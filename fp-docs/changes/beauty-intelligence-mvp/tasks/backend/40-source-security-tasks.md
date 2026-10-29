## 固定来源、许可与受控请求任务

- [x] **Task backend-015: 登记五站六候选入口且默认全部禁用**

**Files:**
- Create: `backend/app/domain/sources.py`、`backend/app/application/sources.py`、`backend/config/sources.json`、`backend/tests/integration/persistence/test_sources.py`
- Extend planned: `backend/app/infrastructure/configuration.py`

**Reasoning:**
- D-013、D-014 的目标清单不能自动变成授权清单；PR TIMES 两入口共享站点身份。

**Depends on:** backend-005

**Interfaces:**
- Consumes: I02 Source/SourceEntry。
- Produces: I15 EntrySpec/load_registry/seed_sources 与静态rss/public_list分支key。
- Contract checks: 五站六入口、同站幂等种子；未核验禁用；不从浏览器添加/修改来源。

**Step 1: Write the failing test**
```python
from app.infrastructure.configuration import load_registry
from app.application.sources import seed_sources
from app.infrastructure.persistence.models import Source, SourceEntry
from sqlalchemy import select

def test_six_entries_start_disabled(db):
    specs = load_registry('config/sources.json')
    seed_sources(db, specs)
    seed_sources(db, specs)
    sources = db.scalars(select(Source)).all()
    entries = db.scalars(select(SourceEntry)).all()
    assert len(sources) == 5 and len(entries) == 6
    assert all(not e.enabled and e.verification_status == 'pending' for e in entries)
    assert len([s for s in specs if s.source_key == 'prtimes']) == 2
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_sources.py::test_six_entries_start_disabled -q`
- Expected: 固定配置与种子函数缺失。

**Step 3: Write minimal implementation**
```python
# sources.json 的精确候选key/URL/kind；初始证据为空、enabled=false。
CANDIDATES = (
    ('prtimes-rss', 'prtimes', 'https://prtimes.jp/index.rdf', 'rss'),
    ('prtimes-beauty', 'prtimes', 'https://prtimes.jp/beauty/', 'public_list'),
    ('happi-rss', 'happi', 'https://www.happi.com/feed/', 'rss'),
    ('qingyan-list', 'qingyan', 'https://www.iqingyan.cn/', 'public_list'),
    ('pbn-list', 'pbn', 'https://www.premiumbeautynews.com/en/', 'public_list'),
    ('cosin-list', 'cosin', 'https://cosinkorea.com/', 'public_list'),
)
```
- CANDIDATES 在模块中只验证配置身份，不建立动态插件系统。kind为候选输入类型，不能证明其结构已验证；公开列表selection初始null，禁止启用。seed_sources仅插入缺失身份，不在每次启动重置已经核验的许可/运行状态；配置改动通过I16显式应用。COSIN未验证RSS不编造RSS地址。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_sources.py::test_six_entries_start_disabled -q`
- Expected: PASS；补测二次seed保留许可与last_success。自审热榜/混合行业/建库限制均不被配置隐藏。

**Step 5: Commit**
```bash
git add backend/app/application/sources.py backend/config/sources.json backend/tests/integration/persistence/test_sources.py
git commit -m "feat: register disabled fixed source candidates"
```

- [x] **Task backend-016: 校验逐入口许可与只读来源状态 API**

**Files:**
- Create: `backend/app/presentation/http/sources.py`
- Extend planned: `backend/app/application/sources.py`、`backend/app/presentation/http/app.py`、`backend/tests/integration/persistence/test_sources.py`

**Reasoning:**
- D-035 的网站汇总不能放行另一个入口，运行错误也不能覆盖授权结论。

**Depends on:** backend-008, backend-015

**Interfaces:**
- Consumes: I08、I15；probe作为外部已执行结果输入，本任务不联网。
- Produces: I16 eligible_entries/apply_verification/sources_out/read_evidence/write_evidence、sources_router；核验CLI于backend-033接通。
- Contract checks: allowed需完整依据，enabled再需probe成功；pending/restricted不启用；网站partial只汇总。

**Step 1: Write the failing test**
```python
from app.application.sources import eligible_entries, sources_out

def test_entry_evidence_is_not_site_permission(db, entry_factory):
    a = entry_factory(verification_status='allowed', verification_reason='允许标题保存',
                      verification_reference='https://example.org/terms', enabled=True)
    b = entry_factory(source_id=a.source_id, url='https://example.org/other',
                      verification_status='pending', enabled=False)
    assert [e.id for e in eligible_entries(db)] == [a.id]
    row = next(s for s in sources_out(db) if s.id == a.source_id)
    assert row.verification_status == 'partial'
    assert next(e for e in row.entries if e.id == b.id).enabled is False
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_sources.py::test_entry_evidence_is_not_site_permission -q`
- Expected: 逐入口候选/汇总尚未实现。

**Step 3: Write minimal implementation**
```python
def eligible_entries(db):
    """仅本入口的许可、依据与启用状态能允许访问。"""
    return db.scalars(select(SourceEntry).where(
        SourceEntry.enabled.is_(True),
        SourceEntry.verification_status == 'allowed',
        SourceEntry.verification_reason.is_not(None),
        SourceEntry.verification_reference.is_not(None))).all()
```
- apply_verification验证SiteEvidence，未许可不probe；只有目标环境probe成功才enabled并保存last_success_at。sources_out逐入口列许可和last_error，聚合网站状态；API GET要求session，任何POST/PUT/DELETE为405/404。read/write_evidence原子写安全JSON；不能接受Cookie/原始响应。补测运行失败不改许可，缺依据/空依据拒绝激活，来源API字段/401。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_sources.py -q`
- Expected: PASS。自审许可与运行字段不混用；初始化样本不冒充正式证据。

**Step 5: Commit**
```bash
git add backend/app/application/sources.py backend/app/presentation/http/sources.py backend/app/presentation/http/app.py backend/tests/integration/persistence/test_sources.py
git commit -m "feat: expose per entry permission and runtime status"
```

- [x] **Task backend-017: 验证每次目标解析并拒绝所有非公网地址**

**Files:**
- Create: `backend/app/infrastructure/http/safe_client.py`、`backend/tests/unit/infrastructure/test_safe_http.py`

**Reasoning:**
- D-026 的SSRF保护必须覆盖域名、解析结果和后续实际连接，而不是只检查URL字面量。

**Depends on:** backend-016

**Interfaces:**
- Consumes: I15 allowlist、I01限值。
- Produces: I17 Target/BlockedTarget/validate_target。
- Contract checks: HTTPS443、无凭据、精确主机、混合DNS拒绝；IP literal/loopback/私网/linklocal/metadata/保留地址拒绝。

**Step 1: Write the failing test**
```python
import pytest
from app.infrastructure.http.safe_client import validate_target, BlockedTarget

@pytest.mark.parametrize('ip', ['127.0.0.1','10.1.1.1','169.254.169.254',
                               '100.64.0.1','::1','fe80::1','192.0.2.1'])
def test_reject_reserved_and_rebinding(ip):
    with pytest.raises(BlockedTarget):
        validate_target('https://allowed.example/feed', {'allowed.example'},
                        lambda host, port: ['8.8.8.8', ip])
    t = validate_target('https://allowed.example/feed', {'allowed.example'},
                        lambda host, port: ['8.8.8.8'])
    assert t.ip == '8.8.8.8' and t.host == 'allowed.example'
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_safe_http.py::test_reject_reserved_and_rebinding -q`
- Expected: 安全目标校验尚未定义。

**Step 3: Write minimal implementation**
```python
def validate_target(url, allowed_hosts, resolve):
    """验证全部解析地址并返回固定连接目标，防止再次DNS解析换目标。"""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.port not in (None, 443):
        raise BlockedTarget('不允许的协议或端口')
    host = (parsed.hostname or '').encode('idna').decode('ascii').lower()
    if parsed.username or parsed.password or host not in allowed_hosts:
        raise BlockedTarget('不允许的目标')
    ips = resolve(host, 443)
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise BlockedTarget('目标不是公网地址')
    return Target(host, 443, urlunsplit(('', '', parsed.path or '/', parsed.query, '')), ips[0])
```
- 拒绝控制字符、反斜线、IP字面量、非法域名和过长URL；normalize allowlist为精确IDNA主机，不允许后缀伪装。resolver去重但验证所有IPv4/IPv6，失败closed。生产resolve_bounded用标准库受限子进程调用getaddrinfo（不使用shell），最多5秒，超时terminate/join回收；这解决socket.getaddrinfo无原生超时且不能遗留无限线程的当前安全问题。测试编码IP、凭据绕过、IPv4映射IPv6、DNS异常/超时与空解析。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_safe_http.py -q`
- Expected: PASS。自审Target.ip是已验证值，消费者不能再按域名重连。

**Step 5: Commit**
```bash
git add backend/app/infrastructure/http/safe_client.py backend/tests/unit/infrastructure/test_safe_http.py
git commit -m "feat: validate approved public egress targets"
```

- [x] **Task backend-018: 固定 TLS 连接地址并约束跳转、体积与时间**

**Files:**
- Extend planned: `backend/app/infrastructure/http/safe_client.py`、`backend/tests/unit/infrastructure/test_safe_http.py`、`backend/tests/conftest.py`

**Reasoning:**
- URL先验检查不足以防DNS重绑定，超大/慢响应也不能占满worker或把截断视为成功。

**Depends on:** backend-017

**Interfaces:**
- Consumes: I17 validate_target/Target。
- Produces: I18 SafeClient/Fetched/Limits/FetchError；T02 http_lab。
- Contract checks: socket只连Target.ip；Host与TLS SNI仍为Target.host；每跳重校验，最多4请求；全部预算受控。

**Step 1: Write the failing test**
```python
import pytest
from app.infrastructure.http.safe_client import SafeClient, Limits, FetchError

def test_pinned_redirect_and_limits(http_lab):
    http_lab.reply('https://allowed.example/a', status=302,
                   headers={'Location': 'https://allowed.example/b'})
    http_lab.reply('https://allowed.example/b', body=b'x' * 17)
    client = SafeClient({'allowed.example'}, http_lab.resolve, http_lab.dial,
                        Limits(max_bytes=16))
    with pytest.raises(FetchError):
        client.fetch('https://allowed.example/a')
    assert all(c.ip == '8.8.8.8' and c.host == 'allowed.example'
               for c in http_lab.connections)
    assert len(http_lab.connections) == 2
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_safe_http.py::test_pinned_redirect_and_limits -q`
- Expected: SafeClient/fake transport尚无实现。

**Step 3: Write minimal implementation**
```python
# dial 的生产实现：socket.connect只消费已验证IP；禁止HTTP库自行按域名重解析。
family = socket.AF_INET6 if ':' in target.ip else socket.AF_INET
raw = socket.socket(family, socket.SOCK_STREAM)
raw.settimeout(limits.connect)
raw.connect((target.ip, target.port))
secure = ssl.create_default_context().wrap_socket(raw, server_hostname=target.host)
connection = http.client.HTTPConnection(target.host, target.port, timeout=limits.read)
connection.sock = secure
connection.request('GET', target.path, headers={
    'Host': target.host, 'Accept-Encoding': 'identity', 'User-Agent': 'PersonalHeadlineReader/1.0'})
```
- SafeClient禁自动redirect/retry，手工最多3跳，每跳重新validate_target并检查总monotonic预算。逐块读取最多max_bytes+1，Content-Length仅作提前拒绝，不作信任依据；拒绝压缩、非200、截断、超时、不支持媒体类型，关闭所有socket。新增私网跳转、循环、SNI不匹配、DNS第二次变化、chunked超限/总超时测试；每一步超时取min(剩余总预算,局部限值)，DNS子进程也受总预算限制；不记录body。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_safe_http.py -q`
- Expected: PASS；fake lab验证连接日志而非真实联网。自审总预算也覆盖DNS/握手/读取，不能只设单次read timeout。

**Step 5: Commit**
```bash
git add backend/app/infrastructure/http/safe_client.py backend/tests/unit/infrastructure/test_safe_http.py backend/tests/conftest.py
git commit -m "feat: pin tls egress and bound source requests"
```
