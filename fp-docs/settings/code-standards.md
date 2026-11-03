# FeaturePilot Project Code Standards

## Rules

### P001 — 固定安全 API 错误包

- Rule ID: P001
- Applies to: 仓库根目录的 Python 后端 `app/`，FastAPI API、middleware、依赖与存储/来源错误边界。
- Rule: 面向浏览器的失败必须使用 `{code,message,request_id}`；不得回显请求原值、原始响应、密码、Cookie、CSRF、SQL、异常正文或堆栈。未知异常日志只允许安全关联标识和异常类型。
- Evidence: `app/core/exceptions.py`、`app/presentation/http/auth.py`、`app/application/ingestion.py` 及独立的 bootstrap/auth/ingest 负向测试共同约束；已确认后端设计要求同一错误契约。

### P002 — 应用导入无外部副作用

- Rule ID: P002
- Applies to: 仓库根目录的 `app/`、`alembic/` 和 `config/` 中的应用入口、router、worker、迁移与配置模块。
- Rule: 导入模块不得联网、迁移/创建数据库、启动 worker、读取真实来源或创建会话；运行副作用只能由显式 factory、CLI、worker loop 或迁移命令触发。
- Evidence: `app/main.py:create_app`、`tests/integration/api/test_bootstrap.py::test_import_does_not_connect_to_network_or_database`，以及 API/worker 独立进程架构。

### P003 — 前端会话和写状态仅以服务器确认为准

- Rule ID: P003
- Applies to: `frontend/` 的 API、session/state、路由与 UI 交互。
- Rule: 业务请求固定同源 `/api`；密码、会话、CSRF 和业务缓存不得写入 Web Storage/IndexedDB；受保护写失败不得自动重放或乐观假报成功，迟到响应不得覆盖更新的登录状态。
- Evidence: `frontend/src/shared/api/client.ts`、`frontend/src/features/auth/session.ts`、`frontend/tests/unit/features/auth/session.spec.ts` 和已确认前端设计的会话/收藏规则。

### P004 — Unit/Mock 证据不等于真实 E2E

- Rule ID: P004
- Applies to: 仓库根目录的后端 `tests/`、`frontend/tests/unit/`、原型证据及 FeaturePilot 执行报告。
- Rule: unit fixture、TestClient、内存 HTTP lab、静态原型、路由拦截或 mock 数据只能证明对应隔离行为；真实 E2E 必须由生产 UI→同源 API→SQLite 链路取得，并如实标注浏览器、环境、mock 状态和清理结果。不得用手填 PASS 或 unit 结果签发视觉/来源/部署/E2E 门禁。
- Evidence: `fp-docs/changes/beauty-intelligence-mvp/.fp-execute/progress.md`、前后端任务计划的 UI/E2E lifecycle，以及当前测试命名和 unit-only 注释。

### P005 — 分层单体依赖只能向内

- Rule ID: P005
- Applies to: 仓库根目录后端的 `app/` 与前端的 `frontend/src/`。
- Rule: 后端 domain 不依赖 application/infrastructure/presentation/runtime，infrastructure 不反向依赖 application/presentation/runtime，application 不依赖 FastAPI/Starlette/presentation/runtime；前端 shared 不依赖 features/app，features 不依赖 app。根入口只作稳定适配器，不复制实现。不得为单一 SQLite 实现或单个函数制造空 repository/service/DI 层。
- Evidence: `tests/unit/test_architecture.py`、`frontend/tests/unit/app/architecture.spec.ts`、`docs/architecture.md`，以及当前分层目录。

## Rule Entry Format

新增已证实规则时，按 appRoot 逐条记录：

### PNNN — <简短规则名>

- Rule ID: PNNN
- Applies to: <appRoot、后端或前端及必要版本范围>
- Rule: <可操作的项目约定>
- Evidence: <项目明确决策或多个独立源码/测试位置及理由>
