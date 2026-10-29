# FeaturePilot Frontend Settings

## Frontend Framework and Source Locations

- Framework: Vue 3.5.44、TypeScript 5.9.3、Vite 7.3.7、Vue Router 4.6.4；直接依赖见 `frontend/package.json`。
- Source roots: `frontend/src/`；应用入口 `frontend/src/app/main.ts`。
- Module layout: `app/` 仅组合根与跨 feature 协调，`features/` 按业务能力组织，`shared/` 保存不依赖 feature 的 API 契约和基础设施；测试镜像这些职责。
- Route locations: `frontend/src/app/router.ts`；生产路由限 `/login`、`/`、`/favorites` 及页面局部 drawer/panel 状态。

## Code Standards

- Built-in preset: `vue`
- Rule resources: `skills/_shared/code-standards/common.md` + `skills/_shared/code-standards/vue.md`
- Applies to: `frontend/`；Vue 3.5.44，证据为 `frontend/package.json` 的直接依赖和 `frontend/src/app/main.ts` 的 `createApp` 入口。
- Project rule sources: `fp-docs/settings/code-standards.md`（适用于 `frontend/` 的规则）
- Confirmed overrides: none

## Component Library and Imports

- Library: 不使用大型 UI 组件库；采用小型 Vue 组件和原生控件。
- Import patterns: 使用 TypeScript/ESM 与相对模块；`shared` 不依赖 `features/app`，`features` 不依赖 `app`，由 `app` 完成组合。业务 HTTP 通过 `frontend/src/shared/api/client.ts` 的固定同源 `/api` 客户端。
- Component prefix: none；组件按职责命名，不建立无当前复用依据的通用组件体系。

## Design Tokens and Styling

- Token/style sources: 用户批准的 change-local `prototype.html`、`fp-docs/settings/prototype-style.md` 与 `frontend/tests/visual/source-map.json`；原型源码和专属证据为 local-only。
- Layout/responsive rules: 浅色编辑式工作台，桌面内容最大 1100px、基础间距 16px；桌面导航约 224px，平板折为顶栏，手机单列且触控目标至少 44px。
- 正式页面不得恢复摘要、正文、成分、研究阶段、上市信息、多来源事件或模拟业务数据。

## Figma / Screenshot Handling

- Design sources: 无 Figma；VS-001 为用户批准的本地原型、桌面/平板/手机静态图和已确认前端设计。
- Mapping rules: 只复用已批准的色彩、结构、控件、卡片和 drawer 层级；新增登录、来源状态及标题版内容需独立 runtime 视觉复核。

## Prototype Base Reference

- Selected app and root: `frontend` / `frontend/`
- Base manifest: `fp-docs/prototype-bases/frontend/manifest.json`（`static-modular`、`no-build`、mock-only、local-only）；change-local legacy `prototype.html` 同样保持 local-only。
- Source/build/preview rules: shared prototype-contract；任何基座或原型操作前实时核对来源、忽略规则和写入授权。

## Preview and Visual Verification

- Local validation: 使用 bundled Node/pnpm 运行 `pnpm --dir frontend run test:unit`、`typecheck`、`build`、`check:artifact`、`source-check`。
- Browser/visual checks: 生产 runtime 固定检查 1440、768、390px；验证键盘、焦点、横向溢出、drawer、图片失败、加载/空/失败/过期状态。
- `runtimeVisualReviewed:false` 只能在实际生产 runtime 独立复核后改变；静态原型截图不能证明最终 UI 通过。

## Unknowns

- 生产 UI-bearing 任务尚未完成；当前构建产物仍不是最终工作台。
- 未登记第三方组件库或生产 design-token 文件。
- 真实 UI→API→SQLite E2E 和独立 runtime 视觉复核尚未执行。
