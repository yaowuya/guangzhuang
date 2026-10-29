# 项目架构与依赖规则

本项目采用分层单体。目标不是复制传统 MVC 文件名，而是在一个进程边界内建立清楚的模块接口：HTTP、后台进程和数据库适配器可以变化，标题、来源许可和任务语义保持集中。

## 后端分层

依赖只能由外向内：

```text
presentation/http ─┐
                   ├─> application ─> domain
runtime ───────────┘         │
                             └─> infrastructure ─> domain/core

core  <───────────────────────────── 所有层
```

| 层 | 职责 | 禁止事项 |
| --- | --- | --- |
| `core` | 运行配置、跨层安全异常 | 不依赖 FastAPI、SQLAlchemy 或业务用例 |
| `domain` | 标题值对象、固定分类、来源身份规则 | 不读文件、不访问网络/数据库、不依赖框架 |
| `application` | 查询、事务、认证、来源许可、任务和调度用例 | 不依赖 FastAPI/Starlette，不向路由暴露 ORM |
| `infrastructure` | SQLAlchemy/SQLite、配置文件、RSS/HTML、安全 HTTP | 不依赖 presentation/runtime；不反向调用应用入口 |
| `presentation/http` | FastAPI 路由、请求解析、依赖和异常映射 | 不承载业务决策，不直接拼装数据库事务 |
| `runtime` | worker 认领、失败结算和常驻循环 | 不暴露 HTTP，不在 API 进程中启动线程 |

`app.main`、`app.worker`、`app.backup` 是运维适配器，不是第二套实现。测试和内部模块使用 canonical 分层路径，只有容器/CLI 依赖这三个稳定入口。

## 深模块原则

- `SafeClient` 隐藏 DNS、SSRF、固定 IP TLS、重定向和体积预算。
- `ingest_entry` 隐藏 fetch→解析→分类→upsert→入口结果提交事务。
- `backup` 隐藏 SQLite 在线快照、schema 校验、轮换、WAL 与原子恢复。
- `sources` 隐藏固定入口、许可证据、运行资格和图片撤销规则。

当前只有 SQLite 一个持久化实现，不创建假想的 repository port、DI container 或一函数一个 class。出现第二种真实适配器时，再在调用方与实现之间建立新 seam。

## 前端结构

```text
src/
├── app/       # Vue 组合根、router、共享实例装配
├── features/  # 按业务能力组织 auth/headlines
└── shared/    # 与业务无关的 HTTP client 和后端契约
```

`shared` 不依赖 `features/app`，`features` 不依赖 `app`。`app` 是唯一组合根。业务状态只保存在内存，服务器继续拥有会话、收藏和任务真相。

## 测试结构

后端测试按验证语义分为：

- `tests/unit`：纯规则、适配器边界和架构依赖方向；
- `tests/integration/api`：真实 FastAPI 路由和权限；
- `tests/integration/persistence`：真实临时 SQLite/Alembic；
- `tests/integration/runtime`：worker、中断和恢复。

前端 `tests/unit` 镜像 `app/features/shared` 的职责。真实生产视觉和零 mock UI→API→SQLite E2E 仍由 FeaturePilot 后续任务独立验收。

## 部署拓扑

`docker-compose.yml` 构建并运行：

```text
Internet -> Caddy/web -> FastAPI api -> SQLite volume
                              |  |
                              |  +-> packaged Vue dist / SPA
                              +----> worker -> approved HTTPS sources
secrets-init -> runtime-secrets -> api/worker
migrate ---------------------------^ (同一 runtime target，一次性)
web-validate -> gateway target (无网络、按需)
```

IMAGE_TAG 必须等于干净提交的完整 Git SHA；仓库只跟踪一个根 Dockerfile。其 runtime target 同时包含 Python 应用和 Vue dist，供 API、worker、migrate、secrets-init 复用；gateway target 固化 Caddyfile。migrate/secrets-init 在常驻进程前完成，只有 Caddy 发布 80/443。详细约束见 [部署手册](<../deploy/README.md>)。
