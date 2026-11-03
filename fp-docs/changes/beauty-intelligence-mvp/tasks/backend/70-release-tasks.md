## 容器、同域 HTTPS 与安全回归任务

- [ ] **Task backend-038: 用唯一根 Dockerfile 构建前端、后端与网关 targets**

> 用户于 2026-10-28 直接要求提供 Docker Compose 部署，本地已预建镜像、Compose 与静态守卫；因 backend-033～037 和目标 Linux 仍未验证，本 owner 保持未勾选。

**Files:**
- Create/extend: `Dockerfile`、`.dockerignore`、`backend/constraints.lock`、`backend/tests/unit/infrastructure/test_deployment.py`
- Extend planned: `backend/pyproject.toml`、`backend/app/worker.py`、`backend/app/runtime/worker.py`、`deploy/README.md`

**Reasoning:**
- D-015/D-038 要求一个构建模块：frontend-builder 产物进入 FastAPI runtime，API/worker/migrate 复用 runtime target，Caddy 使用同文件 gateway target。

**Depends on:** backend-032, backend-033, backend-034, backend-035, backend-036, backend-037

**Interfaces:**
- Consumes: I01、I26、I31/I32；I33–I37的诚实核验记录。
- Produces: I38应用镜像、`python -m app.worker`入口。
- Contract checks: Python3.12、非root、无私密文件/原型进入镜像、所有运行依赖实际可解析；不在API内启动worker。

**Step 1: Write the failing test**
```python
from pathlib import Path

def test_single_dockerfile_builds_frontend_into_non_root_backend():
    dockerfile = Path('Dockerfile').read_text(encoding='utf-8')
    assert 'FROM python:3.12-slim' in dockerfile
    assert 'USER app' in dockerfile
    assert 'pip install' in dockerfile
    ignored = Path('.dockerignore').read_text(encoding='utf-8')
    assert '.env' in ignored and '*.sqlite3' in ignored
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_deployment.py::test_single_dockerfile_builds_frontend_into_non_root_backend -q`
- Expected: 容器文件缺失。

**Step 3: Write minimal implementation**
```dockerfile
FROM node:24-bookworm-slim AS frontend-builder
# frozen pnpm install + typecheck + build + artifact check
FROM python:3.12-slim AS backend-builder
# constrained wheel build
FROM python:3.12-slim AS runtime
COPY --from=frontend-builder /build/frontend/dist /srv/app/static
USER app:app
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
FROM caddy:2-alpine AS gateway
COPY deploy/Caddyfile /etc/caddy/Caddyfile
```
- 唯一根 Dockerfile 同时隐藏 Node 构建、Python wheel、非root runtime 与 gateway 配置复杂度；dist 只复制到 `/srv/app/static`，runtime 不含 Node。根 `.dockerignore` deny-all 后精确放行构建输入，并在末尾重新排除 pycache、env、node_modules、dist、数据库和备份。稳定入口仍只有 `app.main`、`app.worker`、`app.backup`。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_deployment.py::test_single_dockerfile_builds_frontend_into_non_root_backend -q`
- 未来授权容器环境再运行：`docker build --target runtime -t beauty-intelligence:local .`；`docker run --rm beauty-intelligence:local python -c "import app.main, app.worker, app.backup; from app.infrastructure.persistence.models import Base"`
- Expected: PASS，实际镜像导入不联网、不建任务。自审Python依赖与镜像未暗加Redis/模型服务。

**Step 5: Commit**
```bash
git add Dockerfile .dockerignore backend/pyproject.toml backend/app/runtime/worker.py backend/tests/unit/infrastructure/test_deployment.py deploy/README.md
git commit -m "build: package api and serial worker in one image"
```

- [ ] **Task backend-039: 部署 Compose 三服务并由 Caddy 提供唯一 HTTPS 入口**

**Files:**
- Create/extend: `docker-compose.yml`、`deploy/Caddyfile`、`deploy/env.example`、`deploy/.gitignore`、`deploy/init_secrets.py`、`deploy/compose.sh`
- Create: `backend/app/presentation/http/static_frontend.py`、`backend/tests/integration/api/test_static_frontend.py`
- Extend planned: `Dockerfile`、`.dockerignore`、`backend/tests/unit/infrastructure/test_deployment.py`、`backend/app/core/config.py`、`backend/app/presentation/http/app.py`、`backend/app/presentation/http/errors.py`、`backend/app/application/auth.py`、`deploy/README.md`

**Reasoning:**
- D-018、D-021 同源HTTPS是认证前提，不得用另起开发服务或明文公网端口替代。

**Depends on:** backend-038, frontend-001

**Interfaces:**
- Consumes: I38、I06可信网关地址与[frontend-001 构建任务](<../frontend/10-foundation-tasks.md#L5-L58>)的可重建前端源码/锁文件。根 Dockerfile 的 frontend-builder 生成并校验 `dist` 后复制到 FastAPI runtime，不依赖宿主残留目录；最小构建仍不等于完整前端交付。
- Produces: I39 Compose/Caddy边界；部署私密文件路径与PUBLIC_ORIGIN一致。
- Contract checks: 只有Caddy映射80/443；API/worker共享db/backup卷；单worker；/api原路径；静态资源不包含真实密码。

**Step 1: Write the failing test**
```python
from pathlib import Path

def test_compose_builds_one_dockerfile_and_exposes_only_gateway():
    compose = Path('../docker-compose.yml').read_text(encoding='utf-8')
    caddy = Path('../deploy/Caddyfile').read_text(encoding='utf-8')
    assert compose.count('dockerfile: Dockerfile') == 2
    assert 'target: runtime' in compose and 'target: gateway' in compose
    assert '8000:8000' not in compose and 'app.worker' in compose
    assert 'reverse_proxy api:8000' in caddy
    assert all(value not in caddy for value in ('try_files', 'file_server', 'root *'))
    assert 'X-BI-Client-IP' in caddy
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_deployment.py::test_compose_builds_one_dockerfile_and_exposes_only_gateway -q`
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
        header Cache-Control "no-cache"
        reverse_proxy api:8000
    }
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy no-referrer
        Content-Security-Policy "default-src 'self'; img-src https:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    }
}
```
- Compose 使用同一后端 image 运行无网络 secrets-init、一次性 migrate、API 与 worker；API 不 publish 端口，worker 无 HTTP。file secrets 先复制到 UID/GID10001、0400 的 runtime-secrets 卷，API/worker 只读挂载，不能依赖 Compose 未实现的 file-secret uid/gid/mode。根 context 由 `.dockerignore` 精确白名单；同一 Dockerfile 的 Node stage 把 dist 复制进 FastAPI runtime，gateway target 只固化 Caddyfile，无固定 IP 的 web-validate 单独验配置。PUBLIC_ORIGIN 为 HTTPS 精确值；默认网络 172.30.0.0/24、Caddy 地址 172.30.0.2 且 TRUSTED_GATEWAY_IP 同值，冲突时一起调整。
- README 给出秘密生成、`compose config`、构建、migrate、升级前 `app.backup create`、停写恢复和镜像回滚。Caddy 是唯一 80/443 入口，只提供 TLS、安全头、hashed asset 缓存和原样反代；FastAPI 静态模块唯一拥有文件查找与 SPA fallback。不得用旧原型或宿主残留 dist 占位。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/unit/infrastructure/test_deployment.py -q`
- 未来授权部署环境：`sh deploy/compose.sh deploy/.env docker-compose.yml config --quiet`；`sh deploy/compose.sh deploy/.env docker-compose.yml run --rm --no-deps web-validate`
- Expected: 静态与语法PASS，真实证书/页面仍待backend-041。自审X-BI-Client-IP由网关覆盖，HTTP不暴露登录口令。

**Step 5: Commit**
```bash
git add Dockerfile .dockerignore docker-compose.yml deploy/Caddyfile deploy/env.example deploy/README.md backend/app/core/config.py backend/app/presentation/http/app.py backend/app/presentation/http/static_frontend.py backend/tests/integration/api/test_static_frontend.py backend/tests/unit/infrastructure/test_deployment.py
git commit -m "deploy: serve private app through same origin caddy https"
```

- [ ] **Task backend-040: 枚举全路由验证权限、脱敏与导入无副作用**

**Files:**
- Create: `backend/tests/integration/api/test_security_audit.py`
- Extend planned: `backend/app/core/exceptions.py`、`backend/app/application/auth.py`、`backend/app/presentation/http/app.py`

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
- Run: `cd backend && python -m pytest tests/integration/api/test_security_audit.py::test_all_routes_protected_and_redacted -q`
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
- Run: `cd backend && python -m pytest tests/integration/api/test_security_audit.py tests/integration/api/test_auth_api.py tests/unit/infrastructure/test_safe_http.py -q`
- Expected: PASS。自审错误处理不回显Pydantic输入、HTTP body或上游异常文本，源码说明与实际status一致。

**Step 5: Commit**
```bash
git add backend/tests/integration/api/test_security_audit.py backend/app/core/exceptions.py backend/app/application/auth.py backend/app/presentation/http/app.py
git commit -m "test: audit every api permission and redaction boundary"
```
