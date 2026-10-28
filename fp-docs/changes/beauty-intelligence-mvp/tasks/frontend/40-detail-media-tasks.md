## 出处详情和外链媒体任务

- [ ] **Task frontend-011: 打开出处侧栏并恢复焦点、滚动和查询上下文**

**Files:**
- Create: `frontend/src/components/DetailDrawer.vue`、`frontend/src/state/drawer.ts`、`frontend/tests/unit/detail.spec.ts`、`frontend/tests/browser/cases/detail.mjs`。
- Extend planned: `frontend/src/views/WorkspaceView.vue`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: DETAIL-D、DETAIL-M、DETAIL-FAIL 双表。

**Reasoning:**
- 提案4/D-025 要求完整标题和出处侧栏，关闭后不丢条件、位置和操作焦点；不复制原型摘要、成分、日期推断或事件多来源详情。

**Depends on:** frontend-009, frontend-010, backend-012, backend-039

**Interfaces:**
- Consumes: [F05/F08/F09/F11](<05-interfaces.md>)、I12 detail。
- Produces: useDrawer 的 `open(id,opener)`/`close()`、selectedId；DetailDrawer 受保护读取与 close emit。
- Contract checks: ID 正整数、404/401/读错分别反馈；只输出 ArticleOut；关闭不重查／清空原列表，不改 API query；浏览器返回优先关闭面板。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：DETAIL-D/DETAIL-M/DETAIL-FAIL。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { useDrawer } from '../../src/state/drawer'

it('restores the actual opener without scrolling to a new list', () => {
  const opener = document.createElement('button')
  document.body.append(opener)
  opener.focus()
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  vi.spyOn(window, 'scrollY', 'get').mockReturnValue(480)
  const drawer = useDrawer()
  drawer.open(7, opener)
  expect(drawer.selectedId.value).toBe(7)
  drawer.close()
  expect(document.activeElement).toBe(opener)
  expect(window.scrollTo).toHaveBeenLastCalledWith(0, 480)
  opener.remove()
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/detail.spec.ts`
- Expected: drawer 状态缺失。dialog API 的 jsdom shim 只在 unit setup，不能带入 src/browser。

**Step 3: Write minimal implementation**
- Template Outline: 原生 `<dialog aria-labelledby>`→sticky head/关闭→h2标题、source.name、reported_date、已知分类／地区／品类、原文a。只在用户主动点原文时 new tab。012 加图，013 加收藏；不渲染未提供的作者、摘要、研究或发布日期结论。
- Script/State Outline: open 记 opener/scroll，push 同URL的受控 history state panel 标记以支持 back 关层；不向 API 塞 panel 参数，不建新业务路由。详情请求经 session.protect，换ID/关闭取消旧请求，404保持抽屉并解释不存在，401按F04失效。关闭/Escape/cancel/popstate 走同一 cleanup，恢复 focus({preventScroll:true}) 和scroll；原 opener 已卸载时回 main；路由切换清理 history 标记与 body锁，不多退一页。
- Style Outline: 原型 modal width min(590px,100vw)、靠右、100dvh、head/content padding 19/28与24/28；mobile全宽，标题24px/1.6，长URL换行。新标题版区域按 R-S 复核，旧详情业务区不保留。
- Visual / UX Checks: 可见close/title/source/date/link；键盘焦点在dialog内，背景inert；关层保留筛选、页码和scroll；mobile无横溢、44px关闭目标。
- UI/E2E Lifecycle and Evidence: business-flow L-B；真实列表滚动后开详情→核对同条目ID/标题/原文→关闭/Escape/back；无业务写入，cleanup关层恢复URL／滚动并退出。故障需真实授权服务条件；404如果不能通过正常UI安全产生，DETAIL-FAIL对应分支保持 BLOCKED，不用伪造响应或删除DB记录补证。

### Visual Evidence Manifest — frontend-011

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DETAIL-D | R-D共同控件＋R-P modal＋R-S | N/A VS-001 | R-D/R-P/R-S hash | 新标题版drawer/desktop | 原型tokens/R-F；Auto Layout N/A | `/?page=1`（侧栏状态） | 真实标题开/关/返回 | 1440×900 | 1 | zh-CN | light | F-REAL；记录ID和原列表scroll | `.fp-execute/visual/frontend-011/DETAIL-D/reference.png` | `.fp-execute/visual/frontend-011/DETAIL-D/current.png` | missing diff：无批准标题版完整drawer图 | None | 右侧≤590、head/body原型留白、标题/出处/关闭可见；规则与原子样式独立复核 | CLI visual frontend-011/DETAIL-D | core visual | PENDING |
| DETAIL-M | R-M共同控件＋R-P modal＋R-S | N/A VS-001 | R-M/R-P/R-S hash | 新drawer/mobile | 原型tokens/R-F；Auto Layout N/A | `/`（侧栏状态） | 长原语言标题/未知日期 | 390×844 | 1 | zh-CN | light | F-REAL；未知日期实际样本 | `.fp-execute/visual/frontend-011/DETAIL-M/reference.png` | `.fp-execute/visual/frontend-011/DETAIL-M/current.png` | missing diff：按全宽/原子控件规则复核 | None | 全宽100dvh、44关闭、未知不造日期、全部文字/原文可滚动到达 | CLI visual frontend-011/DETAIL-M | core visual | PENDING |
| DETAIL-FAIL | R-D控件＋R-S详情错误 | N/A VS-001 | R-D/R-S hash | drawer读取失败 | 原型tokens/R-F；Auto Layout N/A | `/`（侧栏状态） | 真实故障/404/恢复重试 | 1440×900 | 1 | zh-CN | light | F-FAIL；不注入ID/记录/响应 | `.fp-execute/visual/frontend-011/DETAIL-FAIL/reference.png` | `.fp-execute/visual/frontend-011/DETAIL-FAIL/current.png` | missing diff：按错误与可关闭规则复核 | None | 错误不清背景列表，close/重试仍可达，404不称空库 | CLI visual frontend-011/DETAIL-FAIL | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-011

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-011 | DETAIL-D | 提案4；D-025；同条目详情、原文、关闭/Escape/back、条件与scroll/focus | business-flow | Visual DETAIL-D route | REQUIRED | L-B；真实detail请求和导航run；Mocked Core API:false；关层/退出 | `.fp-execute/e2e/frontend-011/DETAIL-D/coverage-matrix.md` | BLOCKED：未执行真实drawer/navigation |
| frontend-011 | DETAIL-M | R-S详情手机/键盘、长标题/未知日期可达 | business-flow | Visual DETAIL-M route | REQUIRED | L-B；独立review＋真实mobile run；Mocked Core API:false；关层/退出 | `.fp-execute/e2e/frontend-011/DETAIL-M/coverage-matrix.md` | BLOCKED：需真实样本及运行证据 |
| frontend-011 | DETAIL-FAIL | I12 401/404/读错、重试/取消竞态，不破坏列表 | business-flow | Visual DETAIL-FAIL route | REQUIRED | L-B；真实异常/恢复run；Mocked Core API:false；恢复环境/退出 | `.fp-execute/e2e/frontend-011/DETAIL-FAIL/coverage-matrix.md` | BLOCKED：自然404/安全故障条件未取得，不通过API/DB写替代UI |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/detail.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in DETAIL-D DETAIL-M DETAIL-FAIL; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-011 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-011 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-011 --case "$c" --phase e2e || exit 1
done
```
- Expected: 独立视觉review先放行，真实detail/返回/异常和cleanup完整；unit补测opener卸载、请求竞态、cancel、popstate、组件卸载解锁。自审 history 与URL既不制造新业务路由也不后退两次；必要原因注释和事件移除完整。

**Step 5: Commit**
```bash
git add frontend/src/components/DetailDrawer.vue frontend/src/state/drawer.ts frontend/src/views/WorkspaceView.vue frontend/tests/unit/detail.spec.ts frontend/tests/browser/cases/detail.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: add source detail drawer with stable return context"
```

- [ ] **Task frontend-012: 安全打开原文并直连获准图片、失败只降级文字**

**Files:**
- Create: `frontend/src/components/SourceImage.vue`、`frontend/src/utils/external-url.ts`、`frontend/tests/unit/source-image.spec.ts`、`frontend/tests/browser/cases/media.mjs`。
- Extend planned: `frontend/src/components/HeadlineCard.vue`、`frontend/src/components/DetailDrawer.vue`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: MEDIA-ALLOWED、MEDIA-ABSENT、MEDIA-FAIL 双表。

**Reasoning:**
- 提案5/D-026 的图片边界是来源直链，不建设图片服务；外链失败不影响标题／原文，013再验证收藏同样不依赖图片。

**Depends on:** frontend-011, backend-012, backend-039

**Interfaces:**
- Consumes: [F12](<05-interfaces.md>)、ArticleOut.image_url/image_credit/original_url。
- Produces: SourceImage、safeExternalUrl，card/drawer 的安全新标签原文入口。
- Contract checks: img直接第三方HTTPS、no-referrer；不可用／无图各有语义；不凭空创造image许可／作者URL；原文保留全部查询参数，不做代理探测／prefetch。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：MEDIA-ALLOWED/MEDIA-ABSENT/MEDIA-FAIL。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SourceImage from '../../src/components/SourceImage.vue'
import { safeExternalUrl } from '../../src/utils/external-url'

it('falls back to text without rewriting the image to a local proxy', async () => {
  const wrapper = mount(SourceImage, { props: {
    url: 'https://unit.example/image.jpg', credit: 'unit credit', title: 'unit headline' } })
  expect(wrapper.get('img').attributes('src')).toBe('https://unit.example/image.jpg')
  expect(wrapper.get('img').attributes('referrerpolicy')).toBe('no-referrer')
  await wrapper.get('img').trigger('error')
  expect(wrapper.text()).toContain('图片暂不可用')
  expect(safeExternalUrl('javascript:alert(1)', 'original')).toBeNull()
  expect(safeExternalUrl('https://user:secret@unit.example/a', 'image')).toBeNull()
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/source-image.spec.ts`
- Expected: SourceImage/safeExternalUrl 缺失。

**Step 3: Write minimal implementation**
- Template Outline: 有获准URL时 img＋可见署名；error后显示role=status文字，无图只保留简洁文字卡而不预留假大图。只消费image_credit文本，不编造imageOrigin/imageLicense字段。原文a外部来源标记、target=_blank、rel=noopener noreferrer；未知危险URL不生成可点链接。
- Script/State Outline: URL仅防御校验，不改变Article身份、不抓来源HTML；image URL变更复位error；img error只改本组件状态，不改收藏／列表。不得 service worker缓存、canvas抓图、fetch/blob/base64、本地副本、图片代理或失败时下载兜底。safeExternalUrl 不把来源地址改成内部路由。
- Style Outline: 原型媒体容器／圆角和署名字阶，采用来源批准实际图片比例；不复制掌园／肤色球历史样本。无图主次遵循R-S，不用无关图填满。
- Visual / UX Checks: 真图片署名可见；实际拒绝/离线后提示不覆盖标题与原文；mobile长URL/署名可换行；原文只由主动用户点击触发新标签。
- UI/E2E Lifecycle and Evidence: business-flow L-B。正常页面选择后端真实允许且匹配条目的图；只读网络metadata证明图片目标第三方且无本站代理请求。失败用获准真实失效链接／第三方拒绝／真实网络离线再恢复，不route/intercept或替换src。尚无有图许可时MEDIA-ALLOWED和FAIL保持BLOCKED，不能拿原型历史图冒充生产样本。cleanup关闭外部tab、恢复网络、退出；收藏不受图失败的真实验证接续013/019，不在本任务虚构已完成。

### Visual Evidence Manifest — frontend-012

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEDIA-ALLOWED | R-D/R-P媒体原子＋R-S | N/A VS-001 | R-D/R-P/R-S hash | 标题图/署名 | 原型tokens/R-F；Auto Layout N/A；业务图非参考 | `/`（详情） | 获准真实图片/原文新tab | 1440×900 | 1 | zh-CN | light | F-REAL；真实image_url/credit许可依据 | `.fp-execute/visual/frontend-012/MEDIA-ALLOWED/reference.png` | `.fp-execute/visual/frontend-012/MEDIA-ALLOWED/current.png` | missing diff：业务图片不同，只对媒体/署名规范 | None | 署名不截断，图不挡出处/原文；不得声称同一照片像素还原 | CLI visual frontend-012/MEDIA-ALLOWED | core visual | PENDING |
| MEDIA-ABSENT | R-M无图卡＋R-S | N/A VS-001 | R-M/R-S hash | 无图title-only | 原型tokens/R-F；Auto Layout N/A | `/` | image_url=null正常阅读 | 390×844 | 1 | zh-CN | light | F-REAL；真实无图条目 | `.fp-execute/visual/frontend-012/MEDIA-ABSENT/reference.png` | `.fp-execute/visual/frontend-012/MEDIA-ABSENT/current.png` | missing diff：删摘要后按无图层级复核 | None | 单列自然高度，标题/来源/日期可读，无空图占位或历史图 | CLI visual frontend-012/MEDIA-ABSENT | core visual | PENDING |
| MEDIA-FAIL | R-M/R-P image-error＋R-S | N/A VS-001 | R-M/R-P/R-S hash | 真实外链图失败 | 原型tokens/R-F；Auto Layout N/A | `/`（详情） | 失效/拒绝/离线及恢复 | 390×844 | 1 | zh-CN | light | F-REAL＋真实图故障F-FAIL | `.fp-execute/visual/frontend-012/MEDIA-FAIL/reference.png` | `.fp-execute/visual/frontend-012/MEDIA-FAIL/current.png` | missing diff：按错误提示/文字可用规则复核 | None | 失败文字可见且不遮挡标题/原文；无代理/缓存回退 | CLI visual frontend-012/MEDIA-FAIL | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-012

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-012 | MEDIA-ALLOWED | 提案5；D-009/D-026；允许图第三方直链、署名、主动原文、安全属性 | business-flow | Visual MEDIA-ALLOWED route | REQUIRED | L-B；网络metadata＋真实tab导航run；Mocked Core API:false；关tab/退出 | `.fp-execute/e2e/frontend-012/MEDIA-ALLOWED/coverage-matrix.md` | BLOCKED：尚无获许可真实有图样本/运行证据 |
| frontend-012 | MEDIA-ABSENT | 提案5；缺图文字/链接仍可用，不造图片 | business-flow | Visual MEDIA-ABSENT route | REQUIRED | L-B；真实null图条目读取；Mocked Core API:false；退出 | `.fp-execute/e2e/frontend-012/MEDIA-ABSENT/coverage-matrix.md` | BLOCKED：未执行；不拿截图代替真实读取 |
| frontend-012 | MEDIA-FAIL | 提案5；失效/拒绝/离线不代理，文字/出处仍可用 | business-flow | Visual MEDIA-FAIL route | REQUIRED | L-B；真实第三方/网络条件；Mocked Core API:false；恢复网络/关闭tab/退出 | `.fp-execute/e2e/frontend-012/MEDIA-FAIL/coverage-matrix.md` | BLOCKED：缺可安全真实图故障条件，禁止拦截替代 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/source-image.spec.ts tests/unit/detail.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in MEDIA-ALLOWED MEDIA-ABSENT MEDIA-FAIL; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-012 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-012 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-012 --case "$c" --phase e2e || exit 1
done
```
- Expected: 独立视觉review及真实网络/页面/清理均通过才完成；unit另测危险协议、凭据URL、超长/控制符、HTTP原文/HTTPS图片、src切换恢复和不自动导航。自审前后端字段一致，没有新增许可字段、图片服务或业务图内嵌。

**Step 5: Commit**
```bash
git add frontend/src/components/SourceImage.vue frontend/src/utils/external-url.ts frontend/src/components/HeadlineCard.vue frontend/src/components/DetailDrawer.vue frontend/tests/unit/source-image.spec.ts frontend/tests/browser/cases/media.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: use safe direct source images and resilient external links"
```
