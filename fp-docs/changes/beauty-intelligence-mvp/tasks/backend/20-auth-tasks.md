## 单人认证与会话任务

- [x] **Task backend-006: 校验 Argon2id 密码与两级登录限流**

**Files:**
- Create: `backend/app/application/auth.py`、`backend/tests/unit/application/test_password.py`

**Reasoning:**
- D-003、D-026、D-032 的首次登录不能依赖已存在的会话，但必须独立抵抗猜测并拒绝明文配置。

**Depends on:** backend-005

**Interfaces:**
- Consumes: I01 Settings/ApiError。
- Produces: I06 verify_password/LoginLimiter。
- Contract checks: 恒定错误消息、拒绝非Argon2id摘要、5次失败/15分钟与30次/分钟全局上限、受控客户端地址。

**Step 1: Write the failing test**
```python
import pytest
from argon2 import PasswordHasher
from app.application.auth import verify_password, LoginLimiter
from app.core.exceptions import ApiError

def test_argon_and_limits(now):
    encoded = PasswordHasher().hash('test-only-secret')
    assert verify_password('test-only-secret', encoded)
    assert not verify_password('wrong', encoded)
    limiter = LoginLimiter()
    for _ in range(5):
        limiter.check('203.0.113.1', now)
        limiter.failed('203.0.113.1', now)
    with pytest.raises(ApiError, match='尝试过多'):
        limiter.check('203.0.113.1', now)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/unit/application/test_password.py::test_argon_and_limits -q`
- Expected: auth 模块尚无校验/限流实现。

**Step 3: Write minimal implementation**
```python
def verify_password(password, encoded):
    """只验证部署者提供的 Argon2id 摘要，不保存或记录口令。"""
    if not encoded.startswith('$argon2id$'):
        return False
    try:
        return PasswordHasher().verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
```
- LoginLimiter 用线程锁保护时间队列，check 原子清理过期项并计全局尝试，failed 计地址失败。客户端地址只取可信Caddy连接传入且验证过的专用头，其它直连场景取socket peer；不消费任意X-Forwarded-For。补测窗口过期、并发和全局限流。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/unit/application/test_password.py -q`
- Expected: PASS。自审错误日志无 password/hash；限流重启边界不宣传为永久封禁。

**Step 5: Commit**
```bash
git add backend/app/application/auth.py backend/tests/unit/application/test_password.py
git commit -m "feat: protect single user password login"
```

- [x] **Task backend-007: 签发可撤销的 24 小时会话和稳定 CSRF 标记**

**Files:**
- Extend planned: `backend/app/application/auth.py`
- Create: `backend/tests/integration/persistence/test_sessions.py`

**Reasoning:**
- D-017、D-026 要求退出立即失效、多页稳定CSRF，并避免数据库泄露直接等同有效Cookie泄露。

**Depends on:** backend-006

**Interfaces:**
- Consumes: I05 Session、I01 Settings。
- Produces: I07 issue_session/resolve_session/csrf_token/revoke_session。
- Contract checks: tokens随机、库只存SHA-256摘要；24h边界到期；HMAC常量时间比较；查询不旋转CSRF。

**Step 1: Write the failing test**
```python
import pytest
from datetime import timedelta
from app.application.auth import issue_session, resolve_session, csrf_token, revoke_session
from app.core.exceptions import ApiError

def test_expiry_csrf_and_revoke(db, settings, now):
    raw, auth = issue_session(db, settings, now)
    assert auth.expires_at == now + timedelta(hours=24)
    assert auth.csrf_token == csrf_token(raw, settings.csrf_key)
    assert resolve_session(db, raw, settings, now).token_digest != raw
    with pytest.raises(ApiError):
        resolve_session(db, raw, settings, now + timedelta(hours=24))
    revoke_session(db, raw)
    with pytest.raises(ApiError):
        resolve_session(db, raw, settings, now)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_sessions.py::test_expiry_csrf_and_revoke -q`
- Expected: 会话函数缺失。

**Step 3: Write minimal implementation**
```python
def csrf_token(raw, key):
    """由当前令牌派生标记，多页面查询不会让彼此失效。"""
    return hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()

def issue_session(db, settings, now):
    """只向调用者返回一次原始令牌，数据库仅提交其摘要。"""
    raw = secrets.token_urlsafe(32)
    expires = now + timedelta(hours=24)
    db.add(Session(token_digest=hashlib.sha256(raw.encode()).hexdigest(),
                   created_at=now, expires_at=expires))
    db.commit()
    return raw, AuthOut(authenticated=True, expires_at=expires,
                        csrf_token=csrf_token(raw, settings.csrf_key))
```
- AuthOut 在本模块定义，统一UTC输出。resolve 每次查询有效记录，过期不能续期；revoke 按摘要删除并提交。session token为空/随机/过期均统一401。清理到期记录不复活旧Cookie。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/persistence/test_sessions.py -q`
- Expected: PASS；补测两次会话不同、同会话标记稳定、数据库内容不含raw token。自审 HMAC key 不入库。

**Step 5: Commit**
```bash
git add backend/app/application/auth.py backend/tests/integration/persistence/test_sessions.py
git commit -m "feat: add revocable server sessions and csrf"
```

- [x] **Task backend-008: 接通首登、会话查询、退出和业务写保护依赖**

**Files:**
- Create: `backend/app/presentation/http/auth.py`、`backend/tests/integration/api/test_auth_api.py`
- Extend planned: `backend/app/application/auth.py`、`backend/app/presentation/http/app.py`、`backend/tests/conftest.py`

**Reasoning:**
- D-032 的登录特例必须和其余写保护分开，否则首次访问永远不能建立会话。

**Depends on:** backend-007

**Interfaces:**
- Consumes: I06、I07。
- Produces: I08 auth_router/require_session/require_write/require_origin；T01 user_client。
- Contract checks: login无CSRF可成功；错误Origin/JSON/密码/频率正确status；其它写缺任一保护拒绝；Cookie安全属性完整。

**Step 1: Write the failing test**
```python
def test_first_login_and_write_guards(client, settings):
    r = client.post('/api/auth/login', json={'password': 'test-only-secret'},
                    headers={'Origin': settings.public_origin})
    assert r.status_code == 200
    assert 'Secure' in r.headers['set-cookie']
    csrf = r.json()['csrf_token']
    assert client.get('/api/auth/session').json()['csrf_token'] == csrf
    assert client.post('/api/auth/logout', json={},
                       headers={'Origin': settings.public_origin}).status_code == 403
    assert client.post('/api/auth/logout', json={}, headers={
        'Origin': settings.public_origin, 'X-CSRF-Token': csrf}).status_code == 200
    assert client.get('/api/auth/session').status_code == 401
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/integration/api/test_auth_api.py::test_first_login_and_write_guards -q`
- Expected: 登录路由404。

**Step 3: Write minimal implementation**
```python
@auth_router.post('/api/auth/login', name='auth_login')
def login(request: Request, body: LoginIn, db=Depends(get_db)):
    """建立会话前单独验证来源、JSON和限流，不要求旧会话。"""
    settings, now_utc = request.app.state.settings, request.app.state.now()
    limiter = request.app.state.login_limiter
    require_origin(request, settings)
    address = client_address(request, settings)
    limiter.check(address, now_utc)
    if not verify_password(body.password, settings.password_hash):
        limiter.failed(address, now_utc)
        raise ApiError('invalid_credentials', '密码或登录信息无效', 401)
    raw, out = issue_session(db, settings, now_utc)
    response = JSONResponse(out.model_dump(mode='json'))
    response.set_cookie('bi_session', raw, max_age=86400,
                        secure=True, httponly=True, samesite='strict', path='/')
    return response
```
- login专用middleware在body解析之前检查JSON Content-Type/Origin，415与403不暴露字段内容；LoginIn只允许1–1,024字符password且forbid extra，JSON请求体上限16 KiB。create_app把LoginLimiter实例放app.state；client地址按I06可信规则，而非直接信任代理头。require_write先resolve会话，再Origin与constant-time CSRF验证；logout撤销并同Path清Cookie。GET session不改变令牌。增加完整负向参数化测试和24h测试。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/integration/api/test_auth_api.py tests/integration/persistence/test_sessions.py tests/unit/application/test_password.py -q`
- Expected: PASS。自审所有保护依赖的职责说明、顺序与status一致，无登录前会话要求。

**Step 5: Commit**
```bash
git add backend/app/presentation/http/auth.py backend/app/application/auth.py backend/app/presentation/http/app.py backend/tests/conftest.py backend/tests/integration/api/test_auth_api.py
git commit -m "feat: expose guarded same origin authentication"
```
