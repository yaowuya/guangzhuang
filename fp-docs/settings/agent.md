# FeaturePilot Agent Settings

## Purpose

- 为本仓库提供精简的 FeaturePilot 工作流约束；当前源码和命令输出仍优先于缓存信息。
- 需求、设计、任务与执行证据由 `fp-docs/changes/beauty-intelligence-mvp/` 的 canonical artifacts 持有。

## Authoritative Project Docs

- 未检测到根级 `CLAUDE.md`、`AGENTS.md`、`GEMINI.md`、`CURSOR.md` 或对应 Agent 配置文档。
- 当前变更的目标需求以 `fp-docs/changes/beauty-intelligence-mvp/` 下已确认的 PRD、proposal、design 和 tasks 为准。

## Workflow Preferences

- Branching: Unknown；不得仅因当前分支为 `main` 推断项目长期分支策略。
- Commit style: 当前历史一致采用 Conventional Commits 风格前缀，如 `feat:`、`test:`、`build:`；提交前仍核对实际范围。
- Review expectations: 每个 FeaturePilot 任务以唯一 owner checkbox 为完成依据，并同步 `.fp-execute/progress.md` 与双端 overview；真实来源、Linux、视觉和 E2E 门禁不得由 unit/mock 结果替代。

## General Allowed / Forbidden Areas

- Allowed: 在已确认任务范围内修改仓库根目录的后端工程（`app/`、`alembic/`、`config/`、`tests/` 与根级依赖/构建配置）、`frontend/`、`deploy/` 及当前 change 的 FeaturePilot process artifacts。
- Forbidden: 不提交密码、Cookie、CSRF 密钥、私密配置、数据库、备份、`.venv/`、`node_modules/`、`dist/`、`.codegraph/` 或原型 local-only 资产。
- Forbidden: 不以非 canonical `docs/mvp-development-plan.md` 驱动或证明 FeaturePilot 执行。

## General Validation Expectations

- 只报告实际运行过的命令和结果；相关测试、类型检查、构建、artifact/source checks 失败时不得勾选任务。
- 真实来源、云部署和浏览器 E2E 必须使用对应真实环境证据，不能用夹具、路由拦截或手填布尔值替代。

## General Security / Data Notes

- 凭据不进入仓库、日志、响应、原型或测试快照。
- 任何远端连接必须保留 SSH 主机密钥校验；不得用关闭校验绕过指纹冲突。

## Related Domain Settings

- Frontend/UI: `fp-docs/settings/frontend.md`
- Backend/API/Data/Security: `fp-docs/settings/backend.md`
- Project code rules: `fp-docs/settings/code-standards.md`
- Prototype visual constraints: `fp-docs/settings/prototype-style.md`

## Unknowns

- 远端 push/PR 目标和长期分支策略尚未登记。
- 腾讯云服务器当前 SSH 主机指纹尚未带外确认，真实部署与来源 probe 保持阻塞。
