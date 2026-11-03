## 标题读取、分页与组合筛选任务

- [x] **Task frontend-008: 建立可取消、保留旧结果的分页读取 composable**

**Files:**
- Create: `frontend/src/features/headlines/headlines.ts`、`frontend/tests/unit/features/headlines/headlines.spec.ts`。

**Reasoning:**
- D-024/D-025 的页面状态要防止慢旧请求覆盖新筛选；后台刷新失败必须保留上次成功内容，但不能把旧条件结果冒充新查询结果。

**Depends on:** frontend-004, frontend-005

**Interfaces:**
- Consumes: [F03/F04/F05](<05-interfaces.md>)。
- Produces: F08 的 page/filters/loading/refreshing/error/load/reload/applyBookmark；生命周期 onScopeDispose abort。
- Contract checks: 每次读取快照 query、generation，旧响应忽略；bookmarkedOnly 决定 articles/bookmarks，不客户端过滤整库；服务器 total/order/page 原样消费。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。无 UI 模板，Browser replay 不适用；不创建虚构 case。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { createApi } from '../../../../src/shared/api/client'
import { createSession } from '../../../../src/features/auth/session'
import { useHeadlines } from '../../../../src/features/headlines/headlines'
import { articleFixture, authFixture } from './fixtures'

it('keeps confirmed data when a same-query reload fails', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue({ categories: [], regions: [], product_types: [],
    uncategorized_value: '__uncategorized__', unknown_value: '__unknown__' })
  const read = vi.spyOn(api, 'listArticles').mockResolvedValue({
    items: [articleFixture()], total: 1, page: 1, page_size: 20 })
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref({ page: 1, page_size: 20 }), bookmarkedOnly: false }))!
  await state.load()
  read.mockRejectedValueOnce(new Error('unit offline'))
  await state.reload()
  expect(state.page.value?.items).toHaveLength(1)
  expect(state.error.value).toBeTruthy()
  scope.stop()
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/headlines/headlines.spec.ts`
- Expected: useHeadlines 尚不存在。

**Step 3: Write minimal implementation**
- Template Outline: 不适用，本任务仅状态。UI/E2E Applicability：不适用，无产品 UI；009/010/014 承担真实浏览器验收。
- Script/State Outline: 显式 load，不在模块导入时发请求；组件 onMounted/watch 调用。每次捕获序号和 AbortController，finally 只修改仍当前请求的 flags。reload 同 key 保留旧 page；新 query 清旧页并标加载。getFilters 独立请求错误不能把动态选项伪造成空成功。session.protect 处理401，dispose abort；applyBookmark 只应用已确认 bool。
- Style Outline: 不适用。
- Visual / UX Checks: 不生成假 loading／empty 运行图；unit 替身只用于竞态和状态断言。
- UI/E2E Lifecycle and Evidence: 不适用；真实列表状态 case 在009，不以 unit 结果标 E2E covered。

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/headlines/headlines.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`。
- Expected: 补测旧请求迟到、abort、快速翻页、401、首次失败无旧页、同条件刷新保留、filters失败、bookmarks endpoint 和未挂载无网络均通过。
- 自审：不加缓存服务、通用请求状态机或业务本地持久化；注释解释新旧条件结果的不同保留语义。

**Step 5: Commit**
```bash
git add frontend/src/features/headlines/headlines.ts frontend/tests/unit/features/headlines/headlines.spec.ts
git commit -m "feat: add cancellable server paged headline state"
```

- [ ] **Task frontend-009: 展示标题元信息卡、真实列表状态和服务端页码**

**Files:**
- Create: `frontend/src/features/headlines/components/HeadlineList.vue`、`frontend/src/features/headlines/components/HeadlineCard.vue`、`frontend/src/features/headlines/components/PaginationControls.vue`、`frontend/tests/unit/features/headlines/headline-list.spec.ts`、`frontend/tests/browser/cases/reading.mjs`。
- Extend planned: `frontend/src/features/headlines/views/WorkspaceView.vue`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: 下列 LIST case 双表。

**Reasoning:**
- 提案1/3/4和 D-009/D-024/D-037 要求真实标题、未知值与分页；删除摘要和虚构研究区后仍保留原型主次，不以空白补回旧内容。

**Depends on:** frontend-007, frontend-008, backend-012, backend-039, backend-041

**Interfaces:**
- Consumes: [F07/F08/F09](<05-interfaces.md>)；[I12 提供者](<../backend/30-reading-tasks.md#L190-L249>)；[I41 真实许可来源前提](<../backend/80-live-acceptance-tasks.md#L5-L64>)。
- Produces: HeadlineList/Card/PaginationControls 和实际 Workspace 数据绑定。
- Contract checks: 仅 ArticleOut 白名单；未知日期写“报道日期未披露”，不是updated_at；空分类在全部可读；total/page_size 用服务器值；不承诺跨更新快照。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：LIST-D/LIST-T/LIST-M/LIST-EMPTY/LIST-READFAIL。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HeadlineCard from '../../src/components/HeadlineCard.vue'
import { articleFixture } from './fixtures'

it('renders unknown metadata honestly and never restores removed analysis', () => {
  const wrapper = mount(HeadlineCard, { props: { article: articleFixture({
    reported_date: null, category_codes: [], region: null, product_type: null }), featured: true } })
  expect(wrapper.text()).toContain('报道日期未披露')
  expect(wrapper.text()).toContain('未分类')
  expect(wrapper.text()).not.toMatch(/中文要点|研究阶段|首次上市|自动评分/)
  expect(wrapper.findAll('h2 button')).toHaveLength(1)
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/headlines/headline-list.spec.ts`
- Expected: 标题组件缺失。

**Step 3: Write minimal implementation**
- Template Outline: section feed→article→meta/h2 title button/已知分类／日期／source；主按钮 emit open，011 再接 drawer。状态区域分别展示首次加载、真实空库、无匹配、读取错误、保留旧页提示和用户重试。Pagination 使用上一页／下一页＋页码/总条数，不伪装无限加载。012/013 再加入真实图与收藏按钮，不放不可操作假按钮。
- Script/State Outline: Workspace 由 route.query→F05→F08；非法 query 单独错误，不发宽泛查询。page 变更写 URL、滚动到结果标题；按后端页码结果显示，空末页明确提示可回上一有效页，不静默去重后隐藏位移。读取重试是 GET，不触发采集。默认20，E2E可正常URL选择较小合法 page_size 验证翻页，不能 seed 凑满一页。
- Style Outline: 来源F07的12列、首条span8／其它span4、2条各6、1条全宽；tablet首条全宽其余双列、mobile单列；无图自然紧凑，标题换行而非塞回旧摘要高度。
- Visual / UX Checks: 三个viewport没有横溢；来源原语言标题、reported_date、未知标签和总数清楚；加载/空/读错不等同“更新无新增”。
- UI/E2E Lifecycle and Evidence: 全部 business-flow，L-B。真实读取样本必须来自获准worker更新，不从API/DB写入或unit fixture准备；backend-041先确保既有真实标题，完整页面主动刷新闭环在019。空库分支在授权全新隔离真实环境验证（正常迁移、无seed），不能清生产库；读失败通过授权停止真实API／真实只读网络故障，恢复后页面重试。缺真实多条／空库／故障前提时对应条目 BLOCKED。

### Visual Evidence Manifest — frontend-009

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LIST-D | R-D＋R-P＋R-S 标题版 | N/A VS-001 | R-D/R-P/R-S hash | feed首卡／分页 | 原型tokens/R-F；Auto Layout N/A | `/?page=1&page_size=2` | 真实标题／已知和未知元信息 | 1440×900 | 1 | zh-CN | light | F-REAL；记录实际ID/标题/顺序 | `.fp-execute/visual/frontend-009/LIST-D/reference.png` | `.fp-execute/visual/frontend-009/LIST-D/current.png` | missing diff：删摘要且内容不同，区域核对 | None | 1100内容宽、16gap、22圆角、原型标题层级；不补旧分析块 | CLI visual frontend-009/LIST-D | core visual | PENDING |
| LIST-T | R-T＋R-S | N/A VS-001 | R-T/R-S hash | tablet feed | 原型tokens/R-F；Auto Layout N/A | `/` | 真实标题长文本 | 768×1024 | 1 | zh-CN | light | F-REAL；同一次稳定样本 | `.fp-execute/visual/frontend-009/LIST-T/reference.png` | `.fp-execute/visual/frontend-009/LIST-T/current.png` | missing diff：内容删减，按跨度／字阶复核 | None | 首卡全宽、其它双列；标题和出处不截断、不横溢 | CLI visual frontend-009/LIST-T | core visual | PENDING |
| LIST-M | R-M＋R-S | N/A VS-001 | R-M/R-S hash | mobile title card | 原型tokens/R-F；Auto Layout N/A | `/` | 单列真实标题／无图 | 390×844 | 1 | zh-CN | light | F-REAL；无图实际条目 | `.fp-execute/visual/frontend-009/LIST-M/reference.png` | `.fp-execute/visual/frontend-009/LIST-M/current.png` | missing diff：无旧正文，按卡/排版规则复核 | None | 16边距、18圆角、自然卡高、控件44；文字与出处可达 | CLI visual frontend-009/LIST-M | core visual | PENDING |
| LIST-EMPTY | R-D控件＋R-S空状态 | N/A VS-001 | R-D/R-S hash | 首次空／无匹配 | 原型tokens/R-F；Auto Layout N/A | `/` | 全新真实空库、加载、重试入口 | 1440×900 | 1 | zh-CN | light | F-EMPTY；隔离环境标识 | `.fp-execute/visual/frontend-009/LIST-EMPTY/reference.png` | `.fp-execute/visual/frontend-009/LIST-EMPTY/current.png` | missing diff：没有批准空库全画面 | None | h1/nav保留，空文案不假称更新成功，不放假卡 | CLI visual frontend-009/LIST-EMPTY | core visual | PENDING |
| LIST-READFAIL | R-D控件＋R-S错误规则 | N/A VS-001 | R-D/R-S hash | 同条件读错保留 | 原型tokens/R-F；Auto Layout N/A | `/` | 实际读失败／恢复重试 | 1440×900 | 1 | zh-CN | light | F-REAL＋F-FAIL；授权真实服务故障 | `.fp-execute/visual/frontend-009/LIST-READFAIL/reference.png` | `.fp-execute/visual/frontend-009/LIST-READFAIL/current.png` | missing diff：按错误与旧列表并存规则复核 | None | 错误明确、旧标题仍可读、重试可见，不将错误渲染为0条 | CLI visual frontend-009/LIST-READFAIL | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-009

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-009 | LIST-D | 提案1/3/4；D-009/D-024/D-037；分页/总数/NULL/排序/跨页位移 | business-flow | Visual LIST-D route | REQUIRED | L-B；独立review＋真实查询run；Mocked Core API:false；无写入，退出 | `.fp-execute/e2e/frontend-009/LIST-D/coverage-matrix.md` | BLOCKED：需许可真实标题及≥2条翻页；不可seed |
| frontend-009 | LIST-T | R-S tablet/长外语标题可读、真实翻页 | business-flow | Visual LIST-T route | REQUIRED | L-B；独立review＋真实tablet读取；Mocked Core API:false；退出 | `.fp-execute/e2e/frontend-009/LIST-T/coverage-matrix.md` | BLOCKED：未执行真实tablet |
| frontend-009 | LIST-M | R-S mobile/无图可读；分页按钮键盘可达 | business-flow | Visual LIST-M route | REQUIRED | L-B；独立review＋真实mobile读取；Mocked Core API:false；退出 | `.fp-execute/e2e/frontend-009/LIST-M/coverage-matrix.md` | BLOCKED：无图真实样本未取得 |
| frontend-009 | LIST-EMPTY | 提案2；首次加载/真空库/GET重试，不等同无新增 | business-flow | Visual LIST-EMPTY route | REQUIRED | L-B；真实空环境身份与查询结果；Mocked Core API:false；不删除生产数据 | `.fp-execute/e2e/frontend-009/LIST-EMPTY/coverage-matrix.md` | BLOCKED：需获准全新隔离真实服务，无seed/清生产库 |
| frontend-009 | LIST-READFAIL | R-S读失败、权限401、保留已确认页和恢复GET重试 | business-flow | Visual LIST-READFAIL route | REQUIRED | L-B；真实故障/恢复run；Mocked Core API:false；恢复服务并退出 | `.fp-execute/e2e/frontend-009/LIST-READFAIL/coverage-matrix.md` | BLOCKED：需安全故障窗口；不能拦截响应 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/headlines/headline-list.spec.ts tests/unit/features/headlines/headlines.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in LIST-D LIST-T LIST-M LIST-EMPTY LIST-READFAIL; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-009 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-009 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-009 --case "$c" --phase e2e || exit 1
done
```
- Expected: 每 case 独立视觉 review 放行后，真实查询/分页/状态和cleanup齐全；缺前提的 case 保持 BLOCKED。自审无摘要/图片假数据、无客户端再排序、分页数值与URL同步，注释说明跨更新位移边界。

**Step 5: Commit**
```bash
git add frontend/src/features/headlines/components/HeadlineList.vue frontend/src/features/headlines/components/HeadlineCard.vue frontend/src/features/headlines/components/PaginationControls.vue frontend/src/features/headlines/views/WorkspaceView.vue frontend/tests/unit/features/headlines/headline-list.spec.ts frontend/tests/browser/cases/reading.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: render real title metadata and server pagination"
```

- [ ] **Task frontend-010: 组合搜索筛选与地址栏、回退和空结果同步**

**Files:**
- Create: `frontend/src/features/headlines/components/SearchFilters.vue`、`frontend/tests/unit/features/headlines/filters.spec.ts`、`frontend/tests/browser/cases/filters.mjs`。
- Extend planned: `frontend/src/features/headlines/views/WorkspaceView.vue`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: FILTER-COMBINED、FILTER-INVALID 双表。

**Reasoning:**
- 提案4和 D-011/D-025 需要标题／来源搜索、合法动态选项、日期范围和 URL 一致；不沿用原型正文／成分搜索或“最早事件日期”。

**Depends on:** frontend-005, frontend-009, backend-012, backend-039

**Interfaces:**
- Consumes: F05/F08/F10、I12 FiltersOut 和 ArticleQuery。
- Produces: SearchFilters 的 change/reset，Workspace URL→真实请求→可见结果单向同步。
- Contract checks: 分类七枚举和未分类；地区/品类来自filters及unknown_value；日期空值不造时间；筛选page=1；400不静默回全部。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：FILTER-COMBINED/FILTER-INVALID。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchFilters from '../../src/components/SearchFilters.vue'
import { filtersFixture } from './fixtures'

it('emits API names, including the unknown sentinel, not prototype fields', async () => {
  const wrapper = mount(SearchFilters, { props: {
    query: { page: 3, page_size: 20 }, options: filtersFixture() } })
  await wrapper.get('select[name="region"]').setValue('__unknown__')
  expect(wrapper.emitted('change')?.at(-1)).toEqual([{ region: '__unknown__' }])
  expect(wrapper.find('[name="market"]').exists()).toBe(false)
  expect(wrapper.find('input[name="date_from"]').attributes('type')).toBe('date')
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/headlines/filters.spec.ts`
- Expected: SearchFilters 不存在。

**Step 3: Write minimal implementation**
- Template Outline: search form＋q input/清除＋category/region/product_type selects＋原生 date_from/date_to＋应用／清除；mobile 展开筛选组，只有同一套搜索值，不叠两份 DOM 输入。日期标签为“报道日期”，不写“最早报道”。
- Script/State Outline: q 通过提交或清除生效（不引 debounce 服务）；patch 交 changeFilters 清page，router push，watch读取；filters请求失败保留错误和GET重试，不填硬编码市场。校验q/日期／单值非法，后端400保留原条件并解释；浏览器 back/forward 复现组合，详情关闭不动条件。
- Style Outline: R-D toolbar 和 R-M 正文流搜索／44px控件；新增双日期控件保持同样pill/label，窄屏可换行，不绝对定位遮挡h1。
- Visual / UX Checks: 选中值、清除入口、结果数和焦点可见；关键词只提示标题／来源；长动态选项可读；无匹配与首次空库区分。
- UI/E2E Lifecycle and Evidence: business-flow，L-B；正常UI组合合法真实选项、实际日期边界、无匹配词、翻页后改筛选归1、刷新深链、back/forward。手改非法URL可验证400；不注入业务记录。真实样本缺未知／某分类／日期边界时该coverage BLOCKED，不用unit代替。cleanup重置URL并正常退出，无业务写数据。

### Visual Evidence Manifest — frontend-010

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FILTER-COMBINED | R-D/R-M toolbar＋R-S | N/A VS-001 | R-D/R-M/R-S hash | mobile展开筛选 | 原型tokens/R-F；Auto Layout N/A | `/?category=__uncategorized__&region=__unknown__` | 实际选项/日期/组合/清除 | 390×844 | 1 | zh-CN | light | F-REAL；运行时冻结真实选项/条目 | `.fp-execute/visual/frontend-010/FILTER-COMBINED/reference.png` | `.fp-execute/visual/frontend-010/FILTER-COMBINED/current.png` | missing diff：日期控件新增，按规范/共同控件复核 | None | 搜索在正文流、44px控件、选中值和结果清晰，无横溢 | CLI visual frontend-010/FILTER-COMBINED | core visual | PENDING |
| FILTER-INVALID | R-D控件＋R-S校验规则 | N/A VS-001 | R-D/R-S hash | 非法条件／无匹配 | 原型tokens/R-F；Auto Layout N/A | `/?page=0` | 本地校验/真实400/无匹配清除 | 1440×900 | 1 | zh-CN | light | 合法真实库＋手改非法query；不改业务数据 | `.fp-execute/visual/frontend-010/FILTER-INVALID/reference.png` | `.fp-execute/visual/frontend-010/FILTER-INVALID/current.png` | missing diff：按校验与状态规则复核 | None | 错误贴近条件、不悄悄显示全部；清除可达且空文案正确 | CLI visual frontend-010/FILTER-INVALID | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-010

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-010 | FILTER-COMBINED | 提案4；D-011/D-025；q/七类/未知/动态选项/日期含界/页码/URL返回 | business-flow | Visual FILTER-COMBINED route | REQUIRED | L-B；真实筛选请求和结果run；Mocked Core API:false；重置条件/退出 | `.fp-execute/e2e/frontend-010/FILTER-COMBINED/coverage-matrix.md` | BLOCKED：需实际样本覆盖相应分支，未执行 |
| frontend-010 | FILTER-INVALID | D-024/D-025；重复参数/非法日期、400反馈、无匹配/清除/重试 | business-flow | Visual FILTER-INVALID route | REQUIRED | L-B；独立review＋真实URL/HTTP拒绝；Mocked Core API:false；恢复合法URL | `.fp-execute/e2e/frontend-010/FILTER-INVALID/coverage-matrix.md` | BLOCKED：尚无真实页面结果；必需E2E不记N/A |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/headlines/filters.spec.ts tests/unit/features/headlines/query.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in FILTER-COMBINED FILTER-INVALID; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-010 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-010 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-010 --case "$c" --phase e2e || exit 1
done
```
- Expected: 每case独立视觉先通过，真实筛选／回退和边界证据后通过；unit全面参数化不计真实覆盖。自审字段、文案、无正文搜索和无硬编码市场，公共事件／非法值原因说明完整。

**Step 5: Commit**
```bash
git add frontend/src/features/headlines/components/SearchFilters.vue frontend/src/features/headlines/views/WorkspaceView.vue frontend/tests/unit/features/headlines/filters.spec.ts frontend/tests/browser/cases/filters.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: synchronize title filters with url and real server results"
```
