## 3. 工程与纯状态基础任务

本片任务不呈现产品 UI，UI/E2E Applicability 为“不适用：工程／纯状态”，不创建 UI case，不豁免后续页面的 REQUIRED E2E。下列 Expected 均是未来执行目标，不是本轮测试结论。

- [x] **Task frontend-001: 建立独立最小工程、类型和测试入口并构建 frontend/dist**

**Files:**
- Create: `frontend/package.json`、`frontend/pnpm-lock.yaml`、`frontend/pnpm-workspace.yaml`、`frontend/.gitignore`、`frontend/index.html`、`frontend/tsconfig.json`、`frontend/tsconfig.app.json`、`frontend/vite.config.ts`、`frontend/vitest.config.ts`、`frontend/src/main.ts`、`frontend/src/env.d.ts`、`frontend/src/App.vue`、`frontend/src/router/index.ts`、`frontend/scripts/check-artifact.mjs`、`frontend/tests/unit/bootstrap.spec.ts`、`frontend/tests/unit/setup.ts`。
- Build output: `frontend/dist/`，不提交生成物。

**Reasoning:**
- D-005/D-018 需要真实 Vue 构建 owner 先给 Caddy 静态产物，避免 gateway 等 UI、UI 又等 gateway。最小构建没有业务数据，不能冒充完成产品。

**Depends on:** None

**Interfaces:**
- Consumes: [F01 与准确依赖／命令](<05-interfaces.md#27-准确命令与单元测试约定>)。
- Produces: F01、可读取的 frontend/dist/index.html 和本地 assets。
- Contract checks: 不依赖后端、不导入 prototype、无 dev proxy、无业务 mock；单元和 app 类型脚本可独立运行。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：不适用，本任务不是产品 UI。

**Step 1: Write the failing test**
- 仅进入已授权执行后，先创建 package/vitest/setup 最小测试支架，并按 F01 的两条准确 add 命令安装已列新依赖、记录版本和 lockfile。支架不实现待测 main/config。
- 执行期已发现 pnpm 11 的 `ERR_PNPM_IGNORED_BUILDS`：唯一待构建依赖为 Vite 所需 `esbuild@0.28.2`。仅在本项目运行 `"$NODE_EXE" "$PNPM_JS" --dir frontend approve-builds esbuild`，由工具生成项目级 `frontend/pnpm-workspace.yaml` 白名单；禁止 `--all`、全局放行或升级 pnpm。安装故障不算业务 RED。
```ts
import { it, expect } from 'vitest'
import { readFileSync } from 'node:fs'

it('builds a local Vue entry for the gateway, not the prototype', () => {
  const main = readFileSync('src/main.ts', 'utf8')
  expect(main).toContain('createApp')
  expect(main).not.toContain('prototype')
  const vite = readFileSync('vite.config.ts', 'utf8')
  expect(vite).toContain("outDir: 'dist'")
  expect(vite).not.toContain('proxy:')
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/bootstrap.spec.ts`
- Expected: main/config 尚不存在而 ENOENT；不得把缺测试 runner／安装失败当作业务 RED。

**Step 3: Write minimal implementation**
- Template Outline: `index.html` 仅 `#app` 与 `/src/main.ts`；App 仅 RouterView，初始 router routes 为空。没有原型 iframe、模拟标题或产品成功屏。
- Script/State Outline: `createApp(App).use(router).mount('#app')`；package显式 `type:"module"`、Vue插件、TS strict、Vite base `/`/outDir `dist`，依F01配置准确scripts。check-artifact检查dist入口、所有引用assets存在且无prototype/mock/秘密，打印入口/asset图的SHA-256作build identity，后续浏览器校验Caddy所服务的实际同一build；`.gitignore`仅本frontend的node_modules/dist/临时测试输出。
- Style Outline: 本任务不定义产品样式；007 消费已冻结原型 token。
- Visual / UX Checks: 不适用；没有 UI case。最小构建不能作为列表、登录或视觉验收结果。
- UI/E2E Lifecycle and Evidence: 不适用。仅记录真实 RED/GREEN/build 命令及结果，不产生假的 SOURCE_READY／PASS。

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/bootstrap.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run check:artifact`。
- Expected: 全部退出 0，dist/index.html 和实际引用 assets 可由 Caddy 只读消费；不要求后端运行。主代理再把 frontend-001 接为 backend-039 前置。
- 自审：依赖安装只发生在确认后，版本来自实际 lockfile；说明清楚入口与隔离边界，没有引入浏览器包／大 UI 库。后续 UI 改动必须重建 dist。

**Step 5: Commit**
```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/.gitignore frontend/index.html frontend/tsconfig.json frontend/tsconfig.app.json frontend/vite.config.ts frontend/vitest.config.ts frontend/src/main.ts frontend/src/env.d.ts frontend/src/App.vue frontend/src/router/index.ts frontend/scripts/check-artifact.mjs frontend/tests/unit/bootstrap.spec.ts frontend/tests/unit/setup.ts
git commit -m "build: bootstrap independent vue frontend artifact"
```

- [x] **Task frontend-002: 冻结客户批准的原型静态来源和删减边界**

**Files:**
- Create: `frontend/tests/visual/source-map.json`、`frontend/scripts/check-visual-sources.mjs`、`frontend/tests/unit/visual-source.spec.ts`。
- Extend planned: `frontend/package.json`。

**Reasoning:**
- VS-001/D-001 需要可复查静态 source revision；不能拿新运行页填 reference，也不能保留旧摘要等被取消内容来凑像素。

**Depends on:** frontend-001

**Interfaces:**
- Consumes: [F02、来源 hash 表](<01-context.md#12-已读来源冻结事实>)及 R-S。
- Produces: F02，带批准依据、原文件 hash、区域和不可复用字段的 source-map。
- Contract checks: 检查三张图实际存在与尺寸；source 只能指批准原型／静态图／规范，runtime path 不可作为 approved source。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：不适用；只冻结源，不生成目标 UI。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { readFileSync } from 'node:fs'

it('freezes approved static sources without pretending Figma exists', () => {
  const map = JSON.parse(readFileSync('tests/visual/source-map.json', 'utf8'))
  expect(map.override).toBe('VS-001')
  expect(map.figma).toBeNull()
  expect(map.sources.map((s: { key: string }) => s.key)).toEqual(
    ['R-P', 'R-D', 'R-T', 'R-M', 'R-S', 'R-F'])
  expect(map.forbiddenBusinessFields).toContain('summary')
  expect(map.runtimeAsReference).toBe(false)
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/visual-source.spec.ts`
- Expected: source-map 不存在；runner 已由 001 建好。

**Step 3: Write minimal implementation**
- Template Outline: 不适用，无生产模板。
- Script/State Outline: source-map 使用仓库根相对批准路径和真实 hash；R-F 同时登记 font/license 两个文件。脚本用标准 node fs/crypto 复核，拒绝路径逃逸、缺图、变更 hash 和 runtime source；脚本不能改 source 或自行批准新 revision。
- Style Outline: 只记录原型 token/区域，007 再实现；登录/来源/新 drawer 记录“规则＋共同控件参照，非完整像素参考”。
- Visual / UX Checks: 无 UI case；三张静态原图已读事实不是新产品视觉 PASS。
- UI/E2E Lifecycle and Evidence: 不适用；source-check 失败会阻塞后续 SOURCE_READY，而非自行降级为 Figma N/A 后跳验。

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/visual-source.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run source-check`。
- Expected: 实际文件 hash 和受支持区域一致；补测 source-map 指 runtime、缺图、改字节时校验非零。
- 自审：不复制原型 JS/数据进生产，不修改 local-only 原型或插件；注释解释来源图与目标 current 的单向关系。

**Step 5: Commit**
```bash
git add frontend/tests/visual/source-map.json frontend/scripts/check-visual-sources.mjs frontend/tests/unit/visual-source.spec.ts frontend/package.json
git commit -m "test: freeze customer approved prototype visual sources"
```

- [x] **Task frontend-003: 实现精确 DTO 和不自动重放的同源 fetch**

**Files:**
- Create: `frontend/src/api/contracts.ts`、`frontend/src/api/client.ts`、`frontend/tests/unit/api-client.spec.ts`、`frontend/tests/unit/fixtures.ts`。

**Reasoning:**
- D-024/D-026 的字段和错误必须先固定；原型字段不能流入标题版。接口不会靠前端猜枚举或封装重试改变写入语义。

**Depends on:** frontend-001

**Interfaces:**
- Consumes: [后端最终 HTTP 字段](<../backend/05-interfaces.md#http-字段和返回状态>)及 [F03](<05-interfaces.md#2-frontend-interface-and-visual-contract>)。
- Produces: createApi、ApiError 和精确消费 DTO；unit-only fixtures。
- Contract checks: DELETE 无 body；200/202 保留 reused；ErrorOut 非空 code/message/request_id；null 不转换虚构值。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：不适用，fetcher 替身仅 unit 隔离，不能算真实 E2E。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { createApi, ApiError } from '../../src/api/client'

it('sends a same-origin confirmed write once and preserves errors', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ code: 'storage_unavailable', message: '暂不可用', request_id: 'unit-1' }),
    { status: 503, headers: { 'Content-Type': 'application/json' } }))
  const api = createApi(fetcher)
  await expect(api.setBookmark(7, false, 'unit-csrf')).rejects.toBeInstanceOf(ApiError)
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/bookmarks/7')
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
    method: 'DELETE', credentials: 'same-origin', body: undefined,
    headers: expect.objectContaining({ 'X-CSRF-Token': 'unit-csrf' }) })
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/api-client.spec.ts`
- Expected: client 模块不存在；不是把真实请求失败当 RED。

**Step 3: Write minimal implementation**
- Template Outline: 不适用。
- Script/State Outline: DTO 精确复制账本消费类型；轻量内部 request 只接受本模块固定路径；JSON 请求设置 Content-Type，不设置浏览器禁写的 Cookie/Origin。401/403/409/429/503 转 ApiError，网络与非 JSON 错误有安全消息；不记录输入，不捕获 AbortError 伪装失败。方法和签名依 F03 的调用表，写入不自动 retry。
- Style Outline: 不适用。
- Visual / UX Checks: 无 UI case；unit fixtures 文件首注释 `UNIT_ONLY`，不得被 src 或 browser 导入。
- UI/E2E Lifecycle and Evidence: 不适用；仅 API 封装单元测试，没有真实接口通过事实。

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/api-client.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`。
- Expected: 精确方法／body/header/status 测试通过；参数化 login 无 CSRF、refresh 精确 trigger、current null、source entry/site 枚举区别、字段无 summary/body/event_id、外部 API 路径拒绝。
- 自审：无通用 service registry、无响应兜底伪成功，公开方法说明服务器确认边界；不为一次 fetch 引新依赖。

**Step 5: Commit**
```bash
git add frontend/src/api/contracts.ts frontend/src/api/client.ts frontend/tests/unit/api-client.spec.ts frontend/tests/unit/fixtures.ts
git commit -m "feat: add exact same origin api client contracts"
```

- [x] **Task frontend-004: 管理内存服务器会话和失效后的禁止写重放**

**Files:**
- Create: `frontend/src/state/session.ts`、`frontend/src/state/runtime.ts`、`frontend/tests/unit/session.spec.ts`。

**Reasoning:**
- D-017/D-026/D-032 需要首登例外与已登录写保护分开；失效不能保留陈旧 CSRF 或在重登后重新收藏／刷新。

**Depends on:** frontend-003

**Interfaces:**
- Consumes: F03 和后端 I08 AuthOut。
- Produces: [F04](<05-interfaces.md#2-frontend-interface-and-visual-contract>)；路由可观察的状态，不直接耦合 Router。
- Contract checks: ensure 仅 GET 去重；401 清内存；logout 成功后清理，403 不假报退出；凭据/CSRF 不落 storage。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：不适用；真实登录由 006 承担。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { createApi, ApiError } from '../../src/api/client'
import { createSession } from '../../src/state/session'
import { authFixture } from './fixtures'

it('invalidates expired auth without replaying the protected action', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  const session = createSession(api)
  await session.login('unit-password')
  const action = vi.fn().mockRejectedValue(new ApiError(401, 'unauthenticated', '已过期', 'unit-2'))
  await expect(session.protect(action)).rejects.toMatchObject({ status: 401 })
  expect(session.auth.value).toBeNull()
  expect(session.status.value).toBe('expired')
  await session.login('unit-password')
  expect(action).toHaveBeenCalledTimes(1)
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/session.spec.ts`
- Expected: createSession 尚不存在。

**Step 3: Write minimal implementation**
- Template Outline: 不适用。
- Script/State Outline: ref 保存 AuthOut，ensure 的共享 promise 在 finally 清理；protect 只捕获 401 失效并继续抛出，不缓存 action，不自动重登。登录密码只在调用栈和原生输入，提交后清空输入；runtime.ts 只构造单一 api/session，不发网络或自启任务。
- Style Outline: 不适用。
- Visual / UX Checks: 无 UI case；expired 是业务 UI 必须消费的状态，不表示已验证登录屏。
- UI/E2E Lifecycle and Evidence: 不适用；006 的 AUTH-EXPIRED 必须真实服务器会话过期／撤销后浏览器验证。

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/session.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`。
- Expected: ensure 并发只发一次、无会话401、login401/429、logout403/401、过期不重放和 storage 无写入均通过。
- 自审：服务器是权限／到期事实源；状态名只是 UI 提示，没有客户端签发令牌或延长24h。

**Step 5: Commit**
```bash
git add frontend/src/state/session.ts frontend/src/state/runtime.ts frontend/tests/unit/session.spec.ts
git commit -m "feat: keep server session state in memory without write replay"
```

- [x] **Task frontend-005: 规范 URL 查询状态和安全站内返回地址**

**Files:**
- Create: `frontend/src/state/query.ts`、`frontend/tests/unit/query.spec.ts`。

**Reasoning:**
- D-025/D-037 要求回退和深链保持条件，同时不能把非法 URL 静默解释为全部或让 returnTo 跳到外站。

**Depends on:** frontend-003

**Interfaces:**
- Consumes: ArticleQuery/FiltersOut、后端精确查询哨兵。
- Produces: [F05](<05-interfaces.md#2-frontend-interface-and-visual-contract>) 的纯函数。
- Contract checks: 单值重复、page/page_size、日期含边界、category合法值；筛选变更归第一页；q 不改写为全文搜索。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：不适用；010 再验证真实地址栏和业务结果。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { decodeQuery, encodeQuery, changeFilters, safeReturn } from '../../src/state/query'

it('round-trips filters and rejects duplicate values and unsafe return paths', () => {
  expect(decodeQuery(new URLSearchParams('page=2&page=3')).ok).toBe(false)
  const parsed = decodeQuery(new URLSearchParams('q=100%25_&category=__uncategorized__&page=2'))
  if (!parsed.ok) throw new Error(parsed.message)
  expect(parsed.value.q).toBe('100%_')
  expect(changeFilters(parsed.value, { region: '__unknown__' }).page).toBe(1)
  expect(new URLSearchParams(encodeQuery(parsed.value)).get('category')).toBe('__uncategorized__')
  expect(safeReturn('//outside.example/x')).toBe('/')
  expect(safeReturn('/favorites?q=oil')).toBe('/favorites?q=oil')
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/query.spec.ts`
- Expected: query 模块函数缺失。

**Step 3: Write minimal implementation**
- Template Outline: 不适用。
- Script/State Outline: 单一 ArticleQuery 编解码；日期校验真实 YYYY-MM-DD 且 start≤end；只发后端字段，省略空值和默认值；识别重复单值，拒绝非法 category、非正整数页码、容量>100、q>200 Unicode 字符。动态 region/product_type 不新造枚举；手改未知值让后端权威判定。safeReturn 仅 `/` 和 `/favorites`，拒绝 scheme、协议相对、反斜线、控制符和 `/login` 回环。
- Style Outline: 不适用。
- Visual / UX Checks: 无 UI case；URL 不包含密码、csrf、业务缓存或面板详情 DTO。
- UI/E2E Lifecycle and Evidence: 不适用；真实页面清除／返回与非法筛选状态归010。

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/query.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`。
- Expected: 七 category、未知哨兵、重复／未知 key、无效闰日、起止倒置、q边界、默认值和站内地址往返通过；未知非业务参数不转发 API。
- 自审：规范化只服务 URL 结构，不在前端自行分类、casefold 或补造日期。

**Step 5: Commit**
```bash
git add frontend/src/state/query.ts frontend/tests/unit/query.spec.ts
git commit -m "feat: encode valid query state and safe return navigation"
```
