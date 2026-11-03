# 标题版美妆情报台 Frontend Plan

本计划把[提案](<../../proposal.md>)和[已确认前端设计](<../../design/frontend.md>)落为 19 个独立任务。主线是最小构建、同源接口、页面状态、标题阅读、服务器收藏、来源更新和真实浏览器交付。本文生成时只写计划、任务为 0 完成；当前执行状态必须从唯一 owner checkbox、[双端 overview](<../00-overview.md>)、Git 和 `.fp-execute/progress.md` 实时核对，不从本段历史描述推断。

> **For agentic workers:** REQUIRED FLOW: Use `fp-execute` to implement this plan task-by-task. 仅任务 owner 的 task marker 使用 checkbox，执行子步骤不使用 checkbox。本文路径在规划生成时为拟创建目标；执行后是否存在及其内容必须由当前源码和实际证据确认。

## Global Constraints

- **范围**：单人密码登录，不注册；仅标题、来源、原文链接、可得报道日期、已知分类／地区／品类及获准图片外链。七类入口、全部、收藏、详情和只读来源面板构成闭环。不得导入原型样本、摘要、正文、成分、功效、研究阶段、上市信息、跨媒体归并或虚构今日计数。依据：[提案 P-001～P-016](<../../proposal.md#handoff-decision-ledger>)。
- **Framework/runtime**：D-005、D-020、D-025 明确 Vue 3、TypeScript、Vite、Vue Router、小型 Vue 组件和原生控件；不用大型 UI 库、Pinia 或通用插件体系。规划生成时尚无生产 `frontend/`、runner 或规范登记；当前实现和适用规范必须从源码、`fp-docs/manifest.md` 与 `fp-docs/settings/frontend.md` 实时读取，不沿用生成时缺失结论。
- **Script/style conventions**：新工程采用 `<script setup lang="ts">`、显式 props/emits、Vue 默认文本转义、局部 composable 与 CSS；不用 `v-html` 渲染来源 HTML。公开模块／组件说明职责和契约；非显然的会话、请求竞态、收藏确认、焦点恢复和轮询停止规则写原因注释。
- **VS-001 customer-confirmed visual-source override**：用户于 2026-10-27 最新直接明确“前端使用原型”，且 D-001 和 `combined-design-postwrite-confirmation` 已确认。获批[原型](<../../prototype.html>)、其静态截图和[前端设计](<../../design/frontend.md#visual-source>)是本项目视觉基准，而不是 Figma。此例外只覆盖来源类型；不豁免独立视觉审查、来源／当前截图分离、真实 UI/API/持久化 E2E、生命周期、清理和失败阻塞。不修改插件，不声称 `Figma only` 门禁通过，不将未执行 case 标为 PASS。
- **独立来源边界**：只复用原型视觉和已支持交互。登录、来源状态及标题版删减后的完整画面并未逐像素展示；以确认设计的规则和原型原子控件对照共同样式，新增画面在真实实现后独立复核。不得拿目标应用运行截图制作 reference，不要求 Figma，不把旧摘要区域作为必须保留的高度。
- **API owner**：[最终 Backend Interface Ledger](<../backend/05-interfaces.md#backend-interface-ledger>) 唯一拥有 HTTP 字段、枚举和状态。消费 I08/I12/I14/I16/I25/I39；不从[普通计划](<../../../../../docs/mvp-development-plan.md>)推导契约。前端接口表仅拥有适配／调用行为，不改后端 DTO，不新增 source-edit、正文、图片代理、模型或管理接口。
- **认证**：服务器 Secure/HttpOnly/SameSite Cookie，24 小时由服务器到期判定；CSRF 只驻内存。首登 JSON 密码不带旧 CSRF；其它写请求带 `X-CSRF-Token`，浏览器提供同源 Origin。401 清会话并安全返回登录；403 显示拒绝，不伪造已登录；重新登录不自动重放写请求。
- **分页与缺值**：默认 page=1/page_size=20，上限 100；q 上限 200 字符。首页按报道日期／ID 倒序，收藏按收藏时间／条目 ID 倒序，前端不再排序。允许后台更新造成跨页位移，不增加快照。分类空数组为未分类；地区、品类、日期和图片可空，不以 updated_at 或站点国别补造。依据：[I10～I14 与查询枚举](<../backend/05-interfaces.md#数据结构和枚举>)及[后端约束](<../backend/01-context.md#global-constraints>)。
- **来源与图片**：五站六候选入口只读，许可与运行失败分开显示；原始图片由浏览器直连第三方，图片失败只降级文字，收藏及原文仍可用。不得代理、下载、转存、base64 内嵌业务图片或加载原型历史图作生产数据。当前没有任何已启用来源事实；本轮不外联、不启用来源。
- **工程依赖**：frontend-001 证明源码可生成 `frontend/dist/index.html` 和本地 assets；这是最小空壳构建，不是完整产品。生产由根 `Dockerfile` 的 frontend-builder 用 frozen lock 重建并经 `check:artifact` 后复制到 FastAPI runtime 的 `/srv/app/static`，不依赖宿主残留 dist。该任务不依赖 backend-039；真实同域 UI 仍依赖 backend-039 和实际 API owner。最终联验依赖 backend-041，不依赖 backend-045，避免跨端循环。
- **工程质量**：执行者和 reviewer 自行读取插件相对资源 `skills/_shared/engineering-quality.md`、`skills/_shared/ui-e2e-contract.md` 及本计划，并按 workspace contract 解析当前安装根。无客户注释格式时用准确中文文档注释；拒绝无当前依据的层、缓存、开关或抽象。小组件／局部状态的简化 owner 是[前端设计风险节](<../../design/frontend.md#风险迁移发布回滚与监控>)；触发条件是实际跨页面状态重复和维护成本增长，不削减当前响应式、键盘或错误验收。
- **Visual evidence runner**：主代理已核验现有 `playwright-cli 0.1.22` + Chrome 可 open `about:blank` 并 close。无项目 runner，不隐式装浏览器、不改全局配置。frontend-006 显式规划项目内薄封装和局部配置；先读现有 CLI help 核对选项，不以 CLI 可启动宣称业务 E2E 通过。能力失效时进入客户选择门禁，缺可用获批能力则 BLOCKED。
- **安装授权**：Vitest、Vue Test Utils 和 jsdom 在规划时属于拟新增依赖；安装事实与实际版本以 frontend-001 提交、锁文件和 progress 证据为准。所有 pnpm 命令必须用执行时 `load_workspace_dependencies` 返回的 bundled Node 可执行文件和 pnpm 脚本路径，不用当前 PATH 的 Node。规划时核验 bundled Node v24.21.0、Python 3.12.14、pnpm 11.28.5；执行前仍须实时核对。
- **真实 E2E**：所有 interactive/business-flow case 均 REQUIRED，记录 `Mocked Core API: false`。从正常页面登录、刷新取得获准真实标题、收藏、重启回看、取消和清理。禁止 route/intercept、MSW、fixture JSON、业务 store/localStorage 注入、seed、mock module 或绕开 UI 的 API/DB 写入。单元夹具只能在 unit 套件，不能导入真实 browser case。无法安全触发的真实异常保持 BLOCKED，不改 N/A。
- **发布前提**：同域 HTTPS、真实测试口令的安全输入、来源许可、至少一个入口目标环境更新成功、维护／故障演练授权和可复核清理均须由实时证据证明。云发布不能以空库、文档、旧原型、离线测试或一次 CLI smoke 代替；缺前提的 owner task 保持未勾选。

## File Structure

路径均从仓库根解析。Create/Extend 表示各 task 的所有权动作；执行后文件可能已经存在，消费者必须读取当前源码而非按动词推断缺失。同一路径第一次创建后，其它任务只扩展。此表覆盖各任务 Files；case 证据的精确归属和文件名由任务内双表唯一持有。

| Path | Action | Responsibility |
| --- | --- | --- |
| `frontend/package.json`、`frontend/pnpm-lock.yaml`、`frontend/pnpm-workspace.yaml`、`frontend/.gitignore` | create | frontend-001 依赖、准确脚本、生成物隔离；实际安装确认 pnpm 11 拦截 esbuild，仅项目级放行该构建依赖，不放开全部脚本或全局配置 |
| `frontend/index.html`、`frontend/tsconfig.json`、`frontend/tsconfig.app.json` | create | 入口和 TS project；app include 不覆盖 unit |
| `frontend/vite.config.ts`、`frontend/vitest.config.ts` | create | `dist` 静态构建；独立 jsdom 单元配置 |
| `frontend/src/app/main.ts`、`frontend/src/env.d.ts`、`frontend/src/app/App.vue`、`frontend/src/app/router.ts` | create/extend | 最小工程入口；后续真实路由和 shell |
| `frontend/scripts/check-artifact.mjs`、`frontend/tests/unit/app/bootstrap.spec.ts`、`frontend/tests/unit/setup.ts` | create | 最小构建入口测试、资源引用／原型隔离校验 |
| `frontend/tests/visual/source-map.json`、`frontend/scripts/check-visual-sources.mjs`、`frontend/tests/unit/visual/source.spec.ts` | create | frontend-002 冻结来源 hash、区域和允许差异；不生成当前截图 |
| `frontend/src/shared/api/contracts.ts`、`frontend/src/shared/api/client.ts`、`frontend/tests/unit/api/client.spec.ts`、`frontend/tests/unit/fixtures.ts` | create | frontend-003 精确 DTO、同源 fetch、明确 unit-only 夹具 |
| `frontend/src/features/auth/session.ts`、`frontend/src/app/runtime.ts`、`frontend/tests/unit/features/auth/session.spec.ts` | create | frontend-004 内存会话与单一 API 实例 |
| `frontend/src/features/headlines/query.ts`、`frontend/tests/unit/features/headlines/query.spec.ts` | create | frontend-005 URL 编解码及安全返回地址 |
| `frontend/src/features/auth/views/LoginView.vue`、`frontend/src/features/headlines/views/WorkspaceView.vue`、`frontend/tests/unit/features/auth/login.spec.ts` | create/extend | frontend-006 登录与工作台路由容器 |
| `frontend/scripts/browser-case.mjs`、`frontend/tests/browser/cli.config.json`、`frontend/tests/browser/case-registry.mjs`、`frontend/tests/browser/support.mjs`、`frontend/tests/browser/README.md`、`frontend/tests/unit/app/browser-harness.spec.ts` | create/extend | 现有 CLI 薄封装、显式局部配置、case 注册和安全证据说明 |
| `frontend/tests/browser/cases/auth.mjs`、`frontend/tests/browser/cases/navigation.mjs` | create | 006/007 正常页面认证和导航 replay |
| `frontend/src/shared/ui/AppShell.vue`、`frontend/src/shared/ui/NavMenu.vue`、`frontend/src/shared/ui/IconButton.vue`、`frontend/src/shared/ui/StatusNotice.vue` | create/extend | frontend-007 小型共享壳和原生控件 |
| `frontend/src/shared/styles/tokens.css`、`frontend/src/shared/styles/base.css`、`frontend/src/shared/styles/layout.css`、`frontend/src/shared/assets/fonts/instrument-sans.ttf`、`frontend/src/shared/assets/fonts/OFL.txt` | create/extend | frontend-007 来源 token、布局和获准字体许可 |
| `frontend/tests/unit/app/navigation.spec.ts` | create | shell/导航语义测试 |
| `frontend/src/features/headlines/headlines.ts`、`frontend/tests/unit/features/headlines/headlines.spec.ts` | create | frontend-008 分页读取、竞态和状态边界 |
| `frontend/src/features/headlines/components/HeadlineList.vue`、`frontend/src/features/headlines/components/HeadlineCard.vue`、`frontend/src/features/headlines/components/PaginationControls.vue`、`frontend/tests/unit/features/headlines/headline-list.spec.ts`、`frontend/tests/browser/cases/reading.mjs` | create/extend | frontend-009 真实标题列表、缺值、服务端分页及状态 |
| `frontend/src/features/headlines/components/SearchFilters.vue`、`frontend/tests/unit/features/headlines/filters.spec.ts`、`frontend/tests/browser/cases/filters.mjs` | create | frontend-010 动态选项和 URL 组合查询 |
| `frontend/src/features/headlines/components/DetailDrawer.vue`、`frontend/src/features/headlines/drawer.ts`、`frontend/tests/unit/features/headlines/detail.spec.ts`、`frontend/tests/browser/cases/detail.mjs` | create/extend | frontend-011 详情、焦点和返回位置 |
| `frontend/src/features/headlines/components/SourceImage.vue`、`frontend/src/shared/security/external-url.ts`、`frontend/tests/unit/features/headlines/source-image.spec.ts`、`frontend/tests/browser/cases/media.mjs` | create | frontend-012 直连图、出处和安全外链 |
| `frontend/src/features/bookmarks/components/BookmarkButton.vue`、`frontend/src/features/bookmarks/bookmarks.ts`、`frontend/tests/unit/features/bookmarks/bookmarks.spec.ts`、`frontend/tests/browser/cases/bookmarks.mjs` | create/extend | frontend-013 服务端确认、三入口一致及失败保留 |
| `frontend/src/features/bookmarks/views/FavoritesView.vue`、`frontend/tests/unit/features/bookmarks/favorites.spec.ts`、`frontend/tests/browser/cases/favorites.mjs` | create | frontend-014 收藏筛选、顺序、空和取消 |
| `frontend/src/features/sources/components/SourceStatus.vue`、`frontend/src/features/sources/components/SourceRow.vue`、`frontend/src/features/sources/sources.ts`、`frontend/tests/unit/features/sources/sources.spec.ts`、`frontend/tests/browser/cases/sources.mjs` | create | frontend-015 五站六入口许可／运行只读状态 |
| `frontend/src/features/update-jobs/components/UpdateStatus.vue`、`frontend/src/features/update-jobs/update-job.ts`、`frontend/tests/unit/features/update-jobs/update-job.spec.ts`、`frontend/tests/browser/cases/updates.mjs` | create/extend | frontend-016 持久任务 ID、刷新、轮询和失败入口重试 |
| `frontend/src/app/overlay.ts`、`frontend/tests/unit/app/accessibility.spec.ts`、`frontend/tests/browser/cases/accessibility.mjs` | create/extend | frontend-017 统一互斥浮层、手机和键盘收口 |
| `frontend/scripts/check-delivery.mjs`、`frontend/tests/unit/app/delivery-gate.spec.ts` | create | frontend-018 证据只读校验，不替 reviewer 下视觉结论 |
| `frontend/tests/browser/cases/release.mjs`、`frontend/tests/unit/app/release-gate.spec.ts` | create | frontend-019 串行真实业务闭环与最终证据门禁 |
| `frontend/dist/` | build | 本地/CI 构建输出，不提交；生产由根 Dockerfile 的 frontend-builder 生成并复制到 FastAPI runtime `/srv/app/static` |
| `fp-docs/changes/beauty-intelligence-mvp/.fp-execute/visual/` | future evidence | 任务双表声明的 `<task-id>/<case-id>/{manifest.md,reference.png,current.png,diff.png,review.md}`；018 独立总审在 `reviews/frontend-018/review.md` |
| `fp-docs/changes/beauty-intelligence-mvp/.fp-execute/e2e/` | future evidence | 每个 case 的 `coverage-matrix.md`、`manifest.md`、`run.md` 和脱敏浏览器 artifacts；不保存 storageState／口令 |
| `fp-docs/changes/beauty-intelligence-mvp/.fp-execute/frontend-release.md` | future evidence | frontend-019 最终真实联验报告，不代替 owner checkbox |

## 1. Page goal and visual context

### 1.1 形态、输入与浏览器事实

- 磁盘 XOR 已复核：proposal small、frontend design small、两端 design index 一致；proposal/frontend 目录和历史 `design-frontend.md` 不存在。原型仅 standalone HTML，无 `prototype/` 目录；前端 plan 两种形式都不存在。
- 默认先评估 small：19 个任务，每个完整五步 TDD、Template/Script/Style/VisualChecks 预计 55～85 行；连同33个case双表、契约及覆盖映射，完整逻辑计划约1,200～1,900行、100,000～160,000字符，明显超过small硬限。因此直接选择split，不先写monolith，不保留 `plan-frontend.md`。分片按manifest语义顺序消费，每片须≤500行且≤30,000字符；写后实测数量在覆盖片记录。
- `UI design source: customer-approved prototype + static screenshots + confirmed design (VS-001)`；`Figma node: N/A`。`Figma only` 不适用且未通过；本项目不采用 `FUNCTION_SCOPE_ONLY` 降级来否认客户批准的视觉基准。缺 reference/current/独立 review 时，视觉结论仍为 `CANNOT_VERIFY` 并阻塞。
- `Browser capability: local playwright-cli 0.1.22 + Chrome`。仅已有 about:blank smoke 事实；项目浏览器 case、局部配置、真实同域环境和证据都尚未创建。项目局部配置必须明示并经本计划确认后创建，不改变全局工具配置。

### 1.2 已读来源冻结事实

2026-10-27 读取本地 CSS、markup、支持交互和三张真实静态图；以下是磁盘原始字节 SHA-256，不使用 read_image 重编码后的 attachment hash。截图报告时间为 `2026-10-26T08:12:53.351Z`；历史截图未记 DPR／locale，不能倒填。未来 current 统一用 DPR=1、zh-CN、light，并记录字体和操作系统；来源未知环境写明限制。

| Source key | Approved source / region | SHA-256 / revision |
| --- | --- | --- |
| R-P | [prototype.html:12–42](<../../prototype.html#L12-L42>)：token、壳、卡、控件、断点；[markup/交互](<../../prototype.html#L71-L94>) | `eaad55cbf304ccaa3c50d84e3f94e9e3ab1ed9354657490594236c90c1b7ed6c` |
| R-D | [desktop-fold.jpg](<../../.prototype-evidence/taste/inspect/desktop-fold.jpg>)，1440×900；左导航、白主面、toolbar、标题层级 | `e18dbdf9a49265a71a6ca7a386455ce83c8cfaa6b0e6e88cb7d9c7765357bad0` |
| R-T | [tablet-fold.jpg](<../../.prototype-evidence/taste/inspect/tablet-fold.jpg>)，768×1024；折叠导航、主面、混合跨度 | `789ef7e1ef243ff2ef854186c07459c6f5514fed1f8b51423a00a843c3fb8f85` |
| R-M | [mobile-fold.jpg](<../../.prototype-evidence/taste/inspect/mobile-fold.jpg>)，390×844；正文流搜索、44 px 控件、单列卡 | `61947d7ee017a1876e47dbe60601d42e458cf4dc1889b54a1face23c0cd7b260` |
| R-S | [frontend design](<../../design/frontend.md>)，D-001/D-020/D-025 和 Visual Checks；新登录／来源画面的规则来源 | `cb2ee739dc2ad4692c5b33ca3cb5c69f9a73cdbe850216b1b8a52f8155d2d762` |
| R-F | [Instrument Sans 字体](<../../.prototype-evidence/instrument-sans.ttf>)；[OFL 许可](<../../.prototype-evidence/font-license.txt>) | font `b24f1812584816958afcf22e22d08e44318c5e51651e25d2438efdde389b33b1`；license `9e27a72ed30eb49a08678f6a5d6ed98ec7ba5368f541637ee0683ec9134ef966` |
| API-R1 | [最终后端账本](<../backend/05-interfaces.md>)；引用其 I08/I12/I14/I16/I25/I39 | `35659aa3a5881045631fc3b78725d495ab4627a9e5d435e9c41dd075ec0f5d5a` |

原截图的摘要、研究阶段和上市日期必须删去；允许内容高度随标题版自然收缩，不得通过假文字／空白补齐旧卡片。R-P 的 `--paper` 等装饰色不授权重用历史业务图。

### 1.3 Capability and preservation mapping

| Capability / Preservation ID | Required observable result | Owner task | Runtime replay / visual case | Completion rule |
| --- | --- | --- | --- | --- |
| FIGCAP：N/A | 没有 Figma 输入，不创建虚构 FIGCAP ledger | 无 | VS-001 下的原型 case | 不宣称 Figma 能力门禁通过 |
| PRES：N/A | 无旧生产 UI/API；原型 localStorage 与虚构数据不是待保留生产行为 | 无 | 原型只提供视觉和支持交互参照 | 不创建虚构 before/after 证据 |
