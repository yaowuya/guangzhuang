## 容器、同域 HTTPS 与安全回归任务

- [ ] **Task backend-038: 构建共用镜像并区分 API 与 worker 启动命令**

**Files:**
- Create: `backend/Dockerfile`、`backend/.dockerignore`、`backend/tests/test_deployment.py`
- Extend planned: `backend/pyproject.toml`、`backend/app/worker.py`、`deploy/README.md`

**Reasoning:**
- D-015 的容器不是第二套应用；一个API和一个worker复用同一模型、配置与采集逻辑。

**Depends on:** backend-032, backend-033, backend-034, backend-035, backend-036, backend-037

**Interfaces:**
- Consumes: I01、I26、I31/I32；I33–I37的诚实核验记录。
- Produces: I38应用镜像、`python -m app.worker`入口。
- Contract checks: Python3.12、非root、无私密文件/原型进入镜像、所有运行依赖实际可解析；不在API内启动worker。

**Step 1: Write the failing test**
```python
from pathlib import Path

def test_shared_image_and_commands():
    dockerfile = Path('Dockerfile').read_text(encoding='utf-8')
    assert 'FROM python:3.12-slim' in dockerfile
    assert 'USER app' in dockerfile
    assert 'pip install' in dockerfile
    ignored = Path('.dockerignore').read_text(encoding='utf-8')
    assert '.env' in ignored and '*.sqlite3' in ignored
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_deployment.py::test_shared_image_and_commands -q`
- Expected: 容器文件缺失。

**Step 3: Write minimal implementation**
```dockerfile
FROM python:3.12-slim
WORKDIR /srv/app
COPY pyproject.toml ./
COPY app ./app
COPY config ./config
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home app
USER app
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
```
- `.dockerignore`排除.env/密钥/数据库/原型/备份。verification仅在执行验收时单独挂载，不能把许可初始值写死为allowed。worker main从Settings构造生命周期并捕获SIGTERM安全退出；进程中断留running给下次结算，不假造完成。记录解析后的实际依赖版本；不因版本范围可安装就跳过全测试。部署准备时创建数据卷权限10001，不用privileged/root运行应用。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_deployment.py::test_shared_image_and_commands -q`
- 未来授权容器环境再运行：`docker build -t beauty-intel-backend:local ./backend`；`docker run --rm beauty-intel-backend:local python -c "import app.main, app.worker, app.models"`
- Expected: PASS，实际镜像导入不联网、不建任务。自审Python依赖与镜像未暗加Redis/模型服务。

**Step 5: Commit**
```bash
git add backend/Dockerfile backend/.dockerignore backend/pyproject.toml backend/app/worker.py backend/tests/test_deployment.py deploy/README.md
git commit -m "build: package api and serial worker in one image"
```

- [ ] **Task backend-039: 部署 Compose 三服务并由 Caddy 提供唯一 HTTPS 入口**

**Files:**
- Create: `deploy/compose.yaml`、`deploy/Caddyfile`、`deploy/env.example`
- Extend planned: `backend/tests/test_deployment.py`、`backend/app/config.py`、`backend/app/auth.py`、`deploy/README.md`

**Reasoning:**
- D-018、D-021 同源HTTPS是认证前提，不得用另起开发服务或明文公网端口替代。

**Depends on:** backend-038, frontend-001

**Interfaces:**
- Consumes: I38、I06可信网关地址；[frontend-001 构建任务](<../frontend/10-foundation-tasks.md#L5-L58>)产生的 `frontend/dist`。该任务只提供独立最小构建，后续 UI 改动重建同一产物，不将最小构建视为完整前端交付。
- Produces: I39 Compose/Caddy边界；部署私密文件路径与PUBLIC_ORIGIN一致。
- Contract checks: 只有Caddy映射80/443；API/worker共享db/backup卷；单worker；/api原路径；静态资源不包含真实密码。

**Step 1: Write the failing test**
```python
from pathlib import Path

def test_same_origin_compose_contract():
    compose = Path('../deploy/compose.yaml').read_text(encoding='utf-8')
    caddy = Path('../deploy/Caddyfile').read_text(encoding='utf-8')
    assert 'frontend/dist' in compose and '8000:8000' not in compose
    assert 'python -m app.worker' in compose
    assert 'reverse_proxy api:8000' in caddy
    assert 'try_files {path} /index.html' in caddy
    assert 'X-BI-Client-IP' in caddy
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_deployment.py::test_same_origin_compose_contract -q`
- Expected: Compose/Caddy文件尚不存在。

**Step 3: Write minimal implementation**
```caddyfile
{$DOMAIN} {
    @api path /api /api/*
    handle @api {
        reverse_proxy api:8000 {
            header_up -Forwarded
            header_up -X-Forwarded-For
            header_up X-BI-Client-IP {remote_host}
        }
    }
    handle {
        root * /srv
        try_files {path} /index.html
        file_server
    }
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy no-referrer
        Content-Security-Policy "default-src 'self'; img-src https:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    }
}
```
- Compose使用caddy:2、同一个backend image；API不publish端口，worker无HTTP；Caddy把`../frontend/dist`只读挂载/srv。命名持久卷/data、/backups、Caddy证书目录，私密password_hash/csrf_key文件只读挂载/run/secrets。PUBLIC_ORIGIN为https域名精确值；默认专用网络172.30.0.0/24、Caddy地址172.30.0.2且TRUSTED_GATEWAY_IP同值；若目标网络冲突须一起调整并重新测信任边界，不信任整个网段。API仅当socket peer为该地址才采用X-BI-Client-IP，任意客户端同名头不能覆盖。
- README给出空库迁移 `docker compose -f deploy/compose.yaml run --rm api alembic upgrade head`，先备份再升级，证书/DNS/端口和来源核验后才上线。frontend/dist缺失时发布前检查明确失败，不能用旧原型占位；不创建任何前端执行文件。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_deployment.py -q`
- 未来授权部署环境：`docker compose -f deploy/compose.yaml config --quiet`；`docker compose -f deploy/compose.yaml run --rm caddy caddy validate --config /etc/caddy/Caddyfile`
- Expected: 静态与语法PASS，真实证书/页面仍待backend-041。自审X-BI-Client-IP由网关覆盖，HTTP不暴露登录口令。

**Step 5: Commit**
```bash
git add deploy/compose.yaml deploy/Caddyfile deploy/env.example deploy/README.md backend/app/config.py backend/app/auth.py backend/tests/test_deployment.py
git commit -m "deploy: serve private app through same origin caddy https"
```

- [ ] **Task backend-040: 枚举全路由验证权限、脱敏与导入无副作用**

**Files:**
- Create: `backend/tests/test_security_audit.py`
- Extend planned: `backend/app/errors.py`、`backend/app/auth.py`、`backend/app/main.py`

**Reasoning:**
- 分散的正例不足以发现漏挂依赖的路由，所有实际业务边界必须有负向验证。

**Depends on:** backend-039

**Interfaces:**
- Consumes: I08、I12、I14、I16、I25、I39。
- Produces: I40完整路由权限/错误回归；不新增业务endpoint。
- Contract checks: 全部业务读401，写无会话401/缺Origin-CSRF403；登录不误要旧会话；不可信代理头无效；无正文/图片代理/来源编辑路由。

**Step 1: Write the failing test**
```python
import pytest

@pytest.mark.parametrize('path', ['/api/articles','/api/articles/1','/api/filters',
    '/api/bookmarks','/api/sources','/api/update-jobs/current','/api/update-jobs/1'])
def test_all_routes_protected_and_redacted(client, path):
    audited = audit_route_guards(client)
    assert audited[path] == 401
    r = client.get(path)
    assert r.status_code == 401
    assert set(r.json()) == {'code','message','request_id'}
    assert 'Traceback' not in r.text and 'password' not in r.text
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_security_audit.py::test_all_routes_protected_and_redacted -q`
- Expected: FAIL，测试专用audit_route_guards尚未建立，无法完成真实路由枚举与验证；新helper实现后任何漏保护路径仍会断言失败。

**Step 3: Write minimal implementation**
```python
def audit_route_guards(client):
    """请求实际注册的每个业务GET，不只检查手写路径清单。"""
    import re
    from fastapi.routing import APIRoute
    statuses = {}
    for route in client.app.routes:
        if isinstance(route, APIRoute) and route.path.startswith('/api/') and 'GET' in route.methods:
            path = re.sub(r'\{[^}]+\}', '1', route.path)
            statuses[path] = client.get(path).status_code
    assert statuses and all(status == 401 for status in statuses.values())
    return statuses
```
- 加参数化写操作401/403与错误Origin、CSRF不匹配、过期24h、退出后旧Cookie测试。构造包含密码/Cookie/CONTENT_SENTINEL的异常，捕获日志检查无敏感值。API禁用生产docs/openapi公开入口或要求会话，不能漏出业务数据；导入subprocess patch socket为拒绝，确保无来源读取或worker自启。只修当前发现的缺陷。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_security_audit.py tests/test_auth_api.py tests/test_safe_http.py -q`
- Expected: PASS。自审错误处理不回显Pydantic输入、HTTP body或上游异常文本，源码说明与实际status一致。

**Step 5: Commit**
```bash
git add backend/tests/test_security_audit.py backend/app/errors.py backend/app/auth.py backend/app/main.py
git commit -m "test: audit every api permission and redaction boundary"
```
