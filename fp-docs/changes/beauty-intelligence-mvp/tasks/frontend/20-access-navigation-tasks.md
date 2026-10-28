## 登录、真实浏览器入口与导航任务

- [ ] **Task frontend-006: 接通服务器登录、受保护路由和现有 CLI 交付入口**

**Files:**
- Create: `frontend/src/views/LoginView.vue`、`frontend/src/views/WorkspaceView.vue`、`frontend/tests/unit/login.spec.ts`、`frontend/scripts/browser-case.mjs`、`frontend/tests/browser/cli.config.json`、`frontend/tests/browser/case-registry.mjs`、`frontend/tests/browser/support.mjs`、`frontend/tests/browser/README.md`、`frontend/tests/browser/cases/auth.mjs`、`frontend/tests/unit/browser-harness.spec.ts`。
- Extend planned: `frontend/src/router/index.ts`、`frontend/src/App.vue`。
- Future evidence: 本任务下列 case 双表声明的 visual/e2e 文件，不在本轮创建。

**Reasoning:**
- D-003/D-017/D-025/D-032 要求用户通过正常页面首登、看到失败、在过期后保留安全返回上下文；router guard 不替代服务器权限。首个 UI 任务同时把已核验 CLI 落为可复放但不另装 runner 的薄入口。

**Depends on:** frontend-001, frontend-002, frontend-004, frontend-005, backend-008, backend-039

**Interfaces:**
- Consumes: [F04/F05/F06、浏览器和证据命令](<05-interfaces.md>)；[I08](<../backend/20-auth-tasks.md#L129-L193>)、I39。
- Produces: LoginView、createAppRouter、真实工作台路由容器；显式本项目 CLI config/support/registry，不改全局配置。
- Contract checks: login 仅 `{password}` 无旧 CSRF；密码不入 URL/storage/日志；安全站内 returnTo；401/429/403 各有反馈；成功／重登不重放写入。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：本任务 AUTH-BASE/AUTH-FAIL/AUTH-EXPIRED，按 Step 4 的 exact command。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LoginView from '../../src/views/LoginView.vue'
import { createApi } from '../../src/api/client'
import { createSession } from '../../src/state/session'
import { authFixture } from './fixtures'

it('submits the password normally and emits only after server confirmation', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  const login = vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  const wrapper = mount(LoginView, { props: { session: createSession(api), returnTo: '/favorites' } })
  await wrapper.get('input[type=password]').setValue('unit-password')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(login).toHaveBeenCalledWith('unit-password')
  expect(wrapper.emitted('authenticated')).toHaveLength(1)
  expect((wrapper.get('input').element as HTMLInputElement).value).toBe('')
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/login.spec.ts`
- Expected: LoginView 不存在；单元替身只证明 UI 提交契约，不能证明真实登录通过。

**Step 3: Write minimal implementation**
- Template Outline: LoginView→h1＋label/password input（autocomplete=current-password）＋原生 submit＋role=alert/status。无注册、外部身份提供者或“演示登录”。WorkspaceView 只提供认证后的空 main 容器，007/009 继续建设，不用原型占位。
- Script/State Outline: router 为 `/login`、`/`、`/favorites` 配置路由；收藏暂共享 WorkspaceView 容器，014 再替换。守卫 await ensure；401 导向 login+safeReturn。watch expired 转向登录，失效后 clear；submit 单飞、finally 清密码，错误401/429/403 可感知，不显示原始输入。
- CLI Outline: 规划时已读 help 支持 `-s=<name> open <url> --browser chrome --config <file>`、`run-code --filename <file>`、`screenshot --filename <file>`、`resize w h`、`close`。执行时从当前已安装 package/`--help` 重新发现 entry 与版本，不提交本机绝对路径；使用 bundled Node 调用而非任意 system Node。按已核验[局部配置与安全输入合同](<05-interfaces.md#27-准确命令与单元测试约定>)写 browser.chromium/channel chrome/isolated=true/headless=false 和context viewport、deviceScaleFactor=1、locale=zh-CN、colorScheme=light；不装browser/package。wrapper对config、case、origin/env做fail-closed校验，run-code只允许普通DOM操作和只读网络metadata，禁route/request/storage/seed。现有run-code无process/require，不能假定env传密码；由操作者只在可见Chrome正常密码框输入真实口令，脚本自动submit并断言真实结果，不人工判PASS。禁真口令进入CLI参数、源码/临时文件或artifact；没有可用安全输入能力则BLOCKED，禁认证trace/HAR/body输出。测试 harness 的脱敏、防空环境和 finally close；业务 case 不能导入 unit fixtures。
- Style Outline: 暂按 R-P/R-S 的文字、边框、pill 和16 px间距实现；007 移到共享 token，不重做视觉。登录新完整画面无全像素参考，reference 仅共同控件裁片。
- Visual / UX Checks: label、提交中、错误、过期提示和返回上下文可见；键盘 Enter 提交；登录表单宽度适配窄屏；不把凭据写入截图／日志。
- UI/E2E Lifecycle and Evidence: 3 个 business-flow case，均 L-B：SOURCE_READY→STATIC_UI_READY→独立 VISUAL_REVIEW_PASS→INTERACTION_READY→真实 FRONTEND_E2E_PASS；阶段与清理依[共同契约](<05-interfaces.md#26-uie2e-delivery-contract-conventions>)。过期必须真实等到24h或由维护者批准撤销原真实会话，再从页面触发业务访问；不改 Cookie／时钟／API 响应。安全触发不了429／过期则对应 coverage BLOCKED，不能当 N/A。

### Visual Evidence Manifest — frontend-006

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AUTH-BASE | R-D＋R-S 登录规则 | N/A VS-001 | R-D/R-S 冻结hash | 新登录；toolbar 控件裁片 | R-P tokens/R-F；Auto Layout N/A | `/login?returnTo=%2F` | 空输入、提交、真实成功返回 | 1440×900 | 1 | zh-CN | light | 真实测试账号；不记录口令 | `.fp-execute/visual/frontend-006/AUTH-BASE/reference.png` | `.fp-execute/visual/frontend-006/AUTH-BASE/current.png` | missing diff：新增完整画面无同构像素图 | None | 白主面、14px正文、原型边框／pill；label/焦点/提交可见，新增布局独立复核 | CLI visual frontend-006/AUTH-BASE | core visual | PENDING |
| AUTH-FAIL | R-M＋R-S 失败规则 | N/A VS-001 | R-M/R-S 冻结hash | mobile 表单／错误 | R-P tokens/R-F；Auto Layout N/A | `/login` | 真实错误密码／限流拒绝 | 390×844 | 1 | zh-CN | light | 真实失败条件 F-FAIL；错误值不存证据 | `.fp-execute/visual/frontend-006/AUTH-FAIL/reference.png` | `.fp-execute/visual/frontend-006/AUTH-FAIL/current.png` | missing diff：按共同控件和错误规则复核 | None | 错误不靠颜色、44px提交、无溢出；无口令回显 | CLI visual frontend-006/AUTH-FAIL | core visual | PENDING |
| AUTH-EXPIRED | R-D＋R-S 会话规则 | N/A VS-001 | R-D/R-S 冻结hash | expired 提示 | R-P tokens/R-F；Auto Layout N/A | `/login?returnTo=%2Ffavorites` | 真实会话失效／重登 | 1440×900 | 1 | zh-CN | light | 原真实会话到期／批准撤销 | `.fp-execute/visual/frontend-006/AUTH-EXPIRED/reference.png` | `.fp-execute/visual/frontend-006/AUTH-EXPIRED/current.png` | missing diff：无已批准过期全屏图 | None | 明确过期提示、站内上下文保留；不声称原型有完整此画面 | CLI visual frontend-006/AUTH-EXPIRED | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-006

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-006 | AUTH-BASE | D-003/D-017/D-025/D-032；首登无需旧CSRF、成功站内返回、退出 | business-flow | Visual AUTH-BASE route | REQUIRED | L-B；独立review＋e2e manifest/run；Mocked Core API:false；最后正常退出清理 | `.fp-execute/e2e/frontend-006/AUTH-BASE/coverage-matrix.md` | BLOCKED：尚无实现和真实HTTPS登录证据 |
| frontend-006 | AUTH-FAIL | D-026；空值/边界、401/403/429反馈和重复提交 | business-flow | Visual AUTH-FAIL route | REQUIRED | L-B；真实认证拒绝／限流结果；Mocked Core API:false；恢复限流窗口／退出 | `.fp-execute/e2e/frontend-006/AUTH-FAIL/coverage-matrix.md` | BLOCKED：错误／429需安全真实环境，不能mock |
| frontend-006 | AUTH-EXPIRED | D-017/D-025；真实失效重登不重放收藏/刷新写入 | business-flow | Visual AUTH-EXPIRED route | REQUIRED | L-B；真实权限失效和重登请求计数；Mocked Core API:false；注销测试会话 | `.fp-execute/e2e/frontend-006/AUTH-EXPIRED/coverage-matrix.md` | BLOCKED：未执行真实到期／撤销与无写重放验证 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/login.spec.ts tests/unit/session.spec.ts tests/unit/browser-harness.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
- Browser commands（仓库根，环境输入已确认后）：
```bash
for c in AUTH-BASE AUTH-FAIL AUTH-EXPIRED; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-006 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-006 --case "$c" --phase visual || exit 1
  # 在继续前由新鲜只读 reviewer 产生该case的独立review.md；未通过即停止。
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-006 --case "$c" --phase e2e || exit 1
done
```
- Expected: 只有独立视觉通过且全部 REQUIRED 真实认证、权限、导航和清理证据完整才可完成；wrapper 必须读取 review 门禁，不能因注释存在就继续。自审新画面仍待独立复核，未绕过登录、无写重放／凭据 artifact。

**Step 5: Commit**
```bash
git add frontend/src/views/LoginView.vue frontend/src/views/WorkspaceView.vue frontend/src/router/index.ts frontend/src/App.vue frontend/tests/unit/login.spec.ts frontend/scripts/browser-case.mjs frontend/tests/browser/cli.config.json frontend/tests/browser/case-registry.mjs frontend/tests/browser/support.mjs frontend/tests/browser/README.md frontend/tests/browser/cases/auth.mjs frontend/tests/unit/browser-harness.spec.ts
git commit -m "feat: add real session login and guarded browser delivery entry"
```

- [ ] **Task frontend-007: 复用原型原子控件、工作台外壳和七类导航**

**Files:**
- Create: `frontend/src/components/AppShell.vue`、`frontend/src/components/NavMenu.vue`、`frontend/src/components/IconButton.vue`、`frontend/src/components/StatusNotice.vue`、`frontend/src/styles/tokens.css`、`frontend/src/styles/base.css`、`frontend/src/styles/layout.css`、`frontend/src/assets/fonts/instrument-sans.ttf`、`frontend/src/assets/fonts/OFL.txt`、`frontend/tests/unit/navigation.spec.ts`、`frontend/tests/browser/cases/navigation.mjs`。
- Extend planned: `frontend/src/main.ts`、`frontend/src/views/LoginView.vue`、`frontend/src/views/WorkspaceView.vue`、`frontend/tests/browser/case-registry.mjs`。

**Reasoning:**
- D-001/D-020/D-025 的浅色阅读壳、七类／全部／收藏导航与可关闭 mobile 面板先独立落地，不复制演示切换器和虚构统计。

**Depends on:** frontend-002, frontend-006

**Interfaces:**
- Consumes: [F02/F05/F06/F07、样式契约](<05-interfaces.md#23-style-and-responsive-design>)；后端 CategoryCode 固定标签仅用作导航 taxonomy。
- Produces: 小型 AppShell/NavMenu/IconButton/StatusNotice、字体及 token；导航只改变站内路由／category query。
- Contract checks: 七类代码／顺序精确；全部包含未分类；收藏路由不伪装为 category；aria-current、hidden/inert、Escape 和焦点恢复正确。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：NAV-D、NAV-M；只验证真实导航交互，不冒称标题数据已建设。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NavMenu from '../../src/components/NavMenu.vue'

it('emits the backend category code and exposes the active navigation', async () => {
  const wrapper = mount(NavMenu, { props: { activeCategory: 'new_ingredients', routeName: 'workspace' } })
  const controls = wrapper.findAll('button')
  expect(controls.filter(b => b.attributes('data-category')).length).toBe(7)
  const current = wrapper.get('[data-category="new_ingredients"]')
  expect(current.attributes('aria-current')).toBe('page')
  await current.trigger('click')
  expect(wrapper.emitted('navigate')?.[0]).toEqual([{ path: '/', category: 'new_ingredients' }])
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/navigation.spec.ts`
- Expected: NavMenu 模块缺失。

**Step 3: Write minimal implementation**
- Template Outline: AppShell→skip link、aside/nav、topbar、main/sheet/canvas；nav 显示品牌、全部／收藏／七类、真实只读更新时间入口预留 slot，不宣称来源已启用。品牌回全部；搜索 slot 本任务不填假搜索框。
- Script/State Outline: NavMenu emit 站内意图，Workspace 用 Router 和 F05 生成 query，切 category 回第一页；mobile 面板有 opener、Escape、背景点击关闭和焦点圈定，关闭 inert；007 先正确实现，017 再统一互斥浮层。引入 StatusNotice 并替换 Login 的重复原子样式。
- Style Outline: 原型 `.sidebar/.sheet/.canvas/.nav-button/.icon-button` 对应组件局部类，token 精确复用 F07；复制 R-F 字体原字节和 OFL，不依赖原型目录运行时读取。桌面224px/1100px、tablet折叠、mobile正文流与44px目标。
- Visual / UX Checks: 三种宽度层级、品牌和当前项清楚；折叠导航不占焦点；不出现“实图样例／演示场景”、虚构计数或未证实的接入成功标记。
- UI/E2E Lifecycle and Evidence: 两个 interactive case，L-I 完整阶段；真实页面登录后通过正常导航操作，Mocked Core API:false；无业务写数据，清理为关闭面板／恢复起始URL／退出会话。缺真实同域路由时 BLOCKED。

### Visual Evidence Manifest — frontend-007

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NAV-D | R-D＋R-P＋R-S | N/A VS-001 | R-D/R-P/R-S hash | sidebar/sheet/navigation | 原型tokens/R-F；Auto Layout N/A | `/?category=new_ingredients` | 当前分类／收藏往返 | 1440×900 | 1 | zh-CN | light | 真实会话；导航taxonomy非业务样本 | `.fp-execute/visual/frontend-007/NAV-D/reference.png` | `.fp-execute/visual/frontend-007/NAV-D/current.png` | missing diff：标题版内容不同，仅区域对照 | None | sidebar224、内容max1100、gap16；active和focus清晰，无演示按钮 | CLI visual frontend-007/NAV-D | core visual | PENDING |
| NAV-M | R-M＋R-P＋R-S | N/A VS-001 | R-M/R-P/R-S hash | mobile topbar/折叠导航 | 原型tokens/R-F；Auto Layout N/A | `/` | 展开、Escape/背景关闭、选项跳转 | 390×844 | 1 | zh-CN | light | 真实会话；空工作台也不造资讯 | `.fp-execute/visual/frontend-007/NAV-M/reference.png` | `.fp-execute/visual/frontend-007/NAV-M/current.png` | missing diff：展开态由原型CSS/交互规范复核 | None | topbar56、menu触控≥44、面板240；无横溢/隐藏焦点 | CLI visual frontend-007/NAV-M | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-007

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-007 | NAV-D | 提案P-003；R-S导航/路由；全部/收藏/七类、URL和后退 | interactive | Visual NAV-D route | REQUIRED | L-I；独立review＋真实DOM导航run；Mocked Core API:false；还原URL/退出 | `.fp-execute/e2e/frontend-007/NAV-D/coverage-matrix.md` | BLOCKED：未实现/未执行；不要求虚构业务数据 |
| frontend-007 | NAV-M | R-S手机/键盘；展开关闭、inert、焦点恢复、路由选择 | interactive | Visual NAV-M route | REQUIRED | L-I；独立review＋触屏/键盘run；Mocked Core API:false；关闭面板/退出 | `.fp-execute/e2e/frontend-007/NAV-M/coverage-matrix.md` | BLOCKED：未执行真实mobile交互 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/navigation.spec.ts tests/unit/login.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run source-check`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in NAV-D NAV-M; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-007 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-007 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-007 --case "$c" --phase e2e || exit 1
done
```
- Expected: source/current 分离、每 case 独立review通过后才继续 E2E；导航无需虚构文章也可验证。自审 token/字体许可、公开组件职责和焦点原因说明；共享样式改变使006旧视觉结论失效时回拍／复核原 owner case。

**Step 5: Commit**
```bash
git add frontend/src/components/AppShell.vue frontend/src/components/NavMenu.vue frontend/src/components/IconButton.vue frontend/src/components/StatusNotice.vue frontend/src/styles/tokens.css frontend/src/styles/base.css frontend/src/styles/layout.css frontend/src/assets/fonts/instrument-sans.ttf frontend/src/assets/fonts/OFL.txt frontend/src/main.ts frontend/src/views/LoginView.vue frontend/src/views/WorkspaceView.vue frontend/tests/unit/navigation.spec.ts frontend/tests/browser/cases/navigation.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: add prototype grounded shell and accessible navigation"
```
