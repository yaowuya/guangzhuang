# FeaturePilot Backend Settings

## Backend Framework and Source Locations

- Framework: Python 3.12、FastAPI `>=0.115,<1`（当前仓库 venv 已解析 0.162.0）、Pydantic 2、SQLAlchemy 2、Alembic、SQLite。
- Source roots: `backend/app/`；迁移 `backend/alembic/`；测试 `backend/tests/`；依赖与 pytest 配置 `backend/pyproject.toml`。
- API/router locations: `backend/app/api_*.py`；工厂入口 `backend/app/main.py:create_app`；独立 worker 入口 `backend/app/worker.py`。

## Code Standards

- Built-in preset: `none`
- Rule resources: N/A；当前后端不是 Django。
- Applies to: `backend/`；FastAPI/Pydantic 2/SQLAlchemy 2，证据为 `backend/pyproject.toml` 和 `backend/app/main.py`。
- Project rule sources: `fp-docs/settings/code-standards.md`（适用于 `backend/` 的规则）
- Confirmed overrides: none

## API / Service / Data Patterns

- Controller/service patterns: `create_app` 显式挂载小型 router；认证、标题、收藏、来源、任务、采集、worker、调度和备份按当前职责模块分开，不建立动态 provider/plugin 系统。
- Data model/schema/migration conventions: SQLAlchemy 显式模型配合手写 Alembic 版本；SQLite 每连接开启 FK 与 5s busy timeout；短事务和数据库约束为并发最终兜底。
- Request/response/error envelope: 同源 `/api` JSON；错误固定 `{code,message,request_id}`，不得返回请求原值、原始响应、SQL、凭据或堆栈。
- 数据范围: 只保存标题及白名单元信息；不保存正文、摘要、模型输出、图片字节或跨媒体事件。

## Auth / Permissions / Isolation

- Auth/session model: 单人 Argon2id 密码；24h 服务器会话，Cookie 为 `bi_session; HttpOnly; Secure; SameSite=Strict; Path=/`，数据库只存令牌摘要。
- Permission/action naming: 首次登录独立验证精确 Origin、JSON、限流和密码；其余业务接口需会话，写接口另需 Origin 与会话 HMAC CSRF。
- Multi-tenant / workspace / project / account isolation: 单人、单实例，无注册、多人、租户或来源编辑 HTTP API。

## Jobs / Operations / Observability

- Background job patterns: 一个独立串行 worker，数据库持有任务；活动任务、日程和 catchup 由部分唯一索引兜底；每入口结果短事务提交。
- Audit/logging expectations: 只记录 request/job 标识及安全错误类型/短文案；不得记录密码、Cookie、CSRF、原始正文、HTML、响应体或异常堆栈。
- Deployment/migration notes: 目标为 Linux + Docker Compose + Caddy，同域 HTTPS；API 与 worker 共享 SQLite/backup 卷。Windows 本地测试不等价于 Linux `flock`、Compose、HTTPS 或真实来源验收。
- Backup/restore: SQLite online backup，integrity + 七表 + Alembic 校验，最近七份；恢复需停写、独占 application lease、pre-restore 快照和明确损失确认。

## Backend Validation Expectations

- Backend test command/pattern: 仓库 venv 中 `cd backend && python -m pytest -q`，并运行 `python -m compileall -q app tests`、`python -m pip check`；目标 Linux 镜像需重跑适用测试。
- Data/security negative-test expectations: 覆盖 401/403/400、会话过期、并发唯一性、SSRF、固定 IP/TLS、体积/时间上限、事务回滚、中断恢复、备份/恢复和敏感信息脱敏。
- 来源/发布: 每入口许可与运行 probe 分开；至少一个来源在目标云服务器真实更新成功前不得宣称交付。

## Unknowns

- 腾讯云 SSH 主机指纹尚未带外确认，未运行目标 Linux、Compose、HTTPS、Caddy、真实来源、07:30 或恢复演练。
- 五站真实许可/运行结论尚未完成；当前候选均不得仅凭本地可访问性启用。
