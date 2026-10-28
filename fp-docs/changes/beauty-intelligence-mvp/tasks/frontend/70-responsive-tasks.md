## 手机、键盘与浮层收口任务

- [ ] **Task frontend-017: 统一浮层清理并验证全键盘、360px和缩放可达性**

**Files:**
- Create: `frontend/src/state/overlay.ts`、`frontend/tests/unit/accessibility.spec.ts`、`frontend/tests/browser/cases/accessibility.mjs`。
- Extend planned: `frontend/src/components/AppShell.vue`、`frontend/src/components/NavMenu.vue`、`frontend/src/components/DetailDrawer.vue`、`frontend/src/components/SourceStatus.vue`、`frontend/src/components/SearchFilters.vue`、`frontend/src/components/PaginationControls.vue`、`frontend/src/components/BookmarkButton.vue`、`frontend/src/components/UpdateStatus.vue`、`frontend/src/styles/base.css`、`frontend/src/styles/layout.css`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: ACCESS-KBD、ACCESS-MOBILE 双表。

**Reasoning:**
- D-025/D-026 和原型交互要求操作不依赖鼠标、手机不横溢。已有nav/detail/sources是实际三个浮层，共享一个小型互斥清理对象有当前依据，不为未来引入弹窗框架。

**Depends on:** frontend-006, frontend-007, frontend-010, frontend-011, frontend-012, frontend-014, frontend-015, frontend-016

**Interfaces:**
- Consumes: [F07/F10/F11/F13/F15/F16/F17](<05-interfaces.md>)和原型 reduced-motion/focus/mobile 规则。
- Produces: AppShell实例内唯一useOverlay对象，传给当前实际浮层；`.open(kind,{opener,background})`、`.close()`、current ref；卸载也close。
- Contract checks: 浮层互斥；关闭／route change／卸载复原原inert/body overflow，不硬写空字符串；焦点回真实opener或main；手机控件≥44px，无隐藏focus目标。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：ACCESS-KBD/ACCESS-MOBILE；原task case不转移owner，受样式影响的旧证据必须失效并由原owner重新捕获／复核。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { useOverlay } from '../../src/state/overlay'

it('restores prior body and inert state after switching and closing overlays', () => {
  const opener = document.createElement('button')
  const background = document.createElement('main')
  document.body.append(opener, background)
  document.body.style.overflow = 'clip'
  const overlay = useOverlay()
  overlay.open('nav', { opener, background })
  expect(background.inert).toBe(true)
  overlay.open('sources', { opener, background })
  expect(overlay.current.value).toBe('sources')
  overlay.close()
  expect(background.inert).toBe(false)
  expect(document.body.style.overflow).toBe('clip')
  expect(document.activeElement).toBe(opener)
  opener.remove(); background.remove(); document.body.style.overflow = ''
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/accessibility.spec.ts`
- Expected: useOverlay缺失；不能仅用Tab事件unit断言替代真实焦点E2E。

**Step 3: Write minimal implementation**
- Template Outline: 保留现有组件层级和语义；AppShell的skip link直达结果main；各层明确aria-labelledby/expanded/controls；表单label、分页和图标button可访问名稳定。禁止给外层可点击card再嵌可点击全卡。
- Script/State Outline: 互斥状态只支持当前nav/detail/sources；打开先清旧层的事件和锁，再记原值，close幂等恢复。keydown Escape只处理顶层；Tab圈定在真实可见可用控件，背景inert；route变更与scope dispose移除监听／timer。bookmark成功重绘后恢复等价按钮或相邻结果；取消末条落结果heading，不能落body。搜索为同一状态／同一输入语义，不用复制hidden业务表单。
- Style Outline: 1440/768/390继承，额外360×800；640/1100断点不漂移。≥44触控、3px focus、长多语标题和URL正常换行，200%浏览器缩放仍有滚动与关闭入口；prefers-reduced-motion=reduce禁过渡、状态不单靠动画；无大UI库／a11y依赖安装。
- Visual / UX Checks: keyboard正常登录→导航→筛选／分页→开关详情／原文→收藏／取消→来源→刷新／重试；mobile导航／筛选展开、详情全宽、来源滚动；所有控制在对应状态可达，不横向溢出。
- UI/E2E Lifecycle and Evidence: 两个business-flow，L-B。真实服务和账号，仅键盘或普通触控操作；200%须用真实Chrome缩放能力并记录方式，不注入CSS zoom伪装；当前CLI若不能可靠设置则该分支BLOCKED。保持source与current渠道分离；UI焦点/DOM测量不等于独立视觉通过。cleanup通过UI恢复原收藏bool、关浮层/外部tab、恢复缩放/网络/维护条件、退出并close全部本次命名session。

### Visual Evidence Manifest — frontend-017

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACCESS-KBD | R-D/R-P focus＋R-S键盘规则 | N/A VS-001 | R-D/R-P/R-S hash | 键盘当前焦点/浮层 | 原型tokens/R-F；Auto Layout N/A | `/` | 全键盘真实业务/200%缩放 | 1440×900 | 1（缩放另记实测值） | zh-CN | light | F-REAL；真实账号/原bool；reduce motion | `.fp-execute/visual/frontend-017/ACCESS-KBD/reference.png` | `.fp-execute/visual/frontend-017/ACCESS-KBD/current.png` | missing diff：按焦点/可达性规则逐状态复核 | None | 3px可见focus、不落隐藏nav、200%不遮close/主操作；实际缩放DPR单独记录 | CLI visual frontend-017/ACCESS-KBD | core visual | PENDING |
| ACCESS-MOBILE | R-M＋R-P断点＋R-S | N/A VS-001 | R-M/R-P/R-S hash | 360窄屏/面板/筛选 | 原型tokens/R-F；Auto Layout N/A | `/`、`/favorites` | mobile完整导航/详情/收藏/来源 | 360×800 | 1 | zh-CN | light | F-REAL；冻结真实标题和选择条件 | `.fp-execute/visual/frontend-017/ACCESS-MOBILE/reference.png` | `.fp-execute/visual/frontend-017/ACCESS-MOBILE/current.png` | missing diff：R-M为390宽，按相同断点/16边距规则复核360 | None | 无横溢、44px可点、搜索正文流、drawer全宽、长文可达 | CLI visual frontend-017/ACCESS-MOBILE | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-017

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-017 | ACCESS-KBD | R-S VisualChecks/验证；全键盘登录/筛选/详情/收藏/刷新/重试、缩放、reduced-motion、清理 | business-flow | Visual ACCESS-KBD route | REQUIRED | L-B；真实键盘run/焦点序列/请求与结果；Mocked Core API:false；UI恢复原bool/缩放并退出 | `.fp-execute/e2e/frontend-017/ACCESS-KBD/coverage-matrix.md` | BLOCKED：未执行；真实重试/200%能力缺失不记N/A |
| frontend-017 | ACCESS-MOBILE | R-S mobile/焦点/隐藏导航；360px完整真实业务和浮层互斥 | business-flow | Visual ACCESS-MOBILE route | REQUIRED | L-B；真实触控/键盘run和持久结果；Mocked Core API:false；关闭层/UI清理/退出 | `.fp-execute/e2e/frontend-017/ACCESS-MOBILE/coverage-matrix.md` | BLOCKED：未执行真实360px流程 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/accessibility.spec.ts tests/unit/navigation.spec.ts tests/unit/detail.spec.ts tests/unit/favorites.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in ACCESS-KBD ACCESS-MOBILE; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-017 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-017 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-017 --case "$c" --phase e2e || exit 1
done
```
- Expected: 独立视觉review通过后，真实keyboard/mobile/zoom结果和cleanup齐全；共享样式影响到的所有旧case由原owner重建当前build证据。unit补测多次close、resize1100/640、原本inert、opener卸载、route卸载监听释放。自审只支持当前三个浮层，无通用弹窗平台；公共契约与清理原因注释准确。

**Step 5: Commit**
```bash
git add frontend/src/state/overlay.ts frontend/src/components/AppShell.vue frontend/src/components/NavMenu.vue frontend/src/components/DetailDrawer.vue frontend/src/components/SourceStatus.vue frontend/src/components/SearchFilters.vue frontend/src/components/PaginationControls.vue frontend/src/components/BookmarkButton.vue frontend/src/components/UpdateStatus.vue frontend/src/styles/base.css frontend/src/styles/layout.css frontend/tests/unit/accessibility.spec.ts frontend/tests/browser/cases/accessibility.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: close keyboard mobile and overlay lifecycle gaps"
```
