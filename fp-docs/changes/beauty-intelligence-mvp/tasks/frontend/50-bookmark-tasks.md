## 服务器收藏写入和收藏视图任务

- [ ] **Task frontend-013: 只在服务器确认后同步收藏并保留失败前状态**

**Files:**
- Create: `frontend/src/features/bookmarks/components/BookmarkButton.vue`、`frontend/src/features/bookmarks/bookmarks.ts`、`frontend/tests/unit/features/bookmarks/bookmarks.spec.ts`、`frontend/tests/browser/cases/bookmarks.mjs`。
- Extend planned: `frontend/src/features/headlines/components/HeadlineCard.vue`、`frontend/src/features/headlines/components/DetailDrawer.vue`、`frontend/src/features/headlines/views/WorkspaceView.vue`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: BOOKMARK-CONFIRM、BOOKMARK-FAIL、BOOKMARK-IMAGEFAIL 双表。

**Reasoning:**
- 提案6/D-036 要求列表、详情和写结果一致，保存失败保持最后成功状态；不能沿用原型 localStorage，也不能用乐观图标伪报保存成功。

**Depends on:** frontend-011, frontend-012, backend-014, backend-039

**Interfaces:**
- Consumes: [F03/F04/F08/F11/F13](<05-interfaces.md>)、[I14](<../backend/30-reading-tasks.md#L314-L369>)。
- Produces: createBookmarks、BookmarkButton 和已挂载列表／详情的 confirmed bool 更新。
- Contract checks: ID单飞；PUT `{}`/DELETE无body带内存CSRF；只按 BookmarkOut.article_id/bookmarked 更新；503/401/403保留原bool；不缓存重放写入。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：BOOKMARK-CONFIRM/BOOKMARK-FAIL/BOOKMARK-IMAGEFAIL；收藏视图第三入口由014接入同一契约。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { createApi, ApiError } from '../../../../src/shared/api/client'
import { createSession } from '../../../../src/features/auth/session'
import { createBookmarks } from '../../../../src/features/bookmarks/bookmarks'
import { articleFixture, authFixture } from './fixtures'

it('keeps the confirmed bookmark when storage rejects a write', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'setBookmark').mockRejectedValue(
    new ApiError(503, 'storage_unavailable', '暂不可用', 'unit-3'))
  const session = createSession(api)
  await session.login('unit-only')
  const onConfirmed = vi.fn()
  const state = createBookmarks({ api, session, onConfirmed })
  const article = articleFixture({ bookmarked: true })
  await state.set(article, false)
  expect(onConfirmed).not.toHaveBeenCalled()
  expect(article.bookmarked).toBe(true)
  expect(state.error.value.get(article.id)).toBeTruthy()
  expect(state.pending.value.has(article.id)).toBe(false)
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/bookmarks/bookmarks.spec.ts`
- Expected: createBookmarks 缺失；单元503替身不是所需真实失败证据。

**Step 3: Write minimal implementation**
- Template Outline: card/footer与drawer/actions复用 BookmarkButton；原生button aria-pressed、可访问名包含标题；pending禁重复，错误role=alert贴近操作，不吞掉主标题点击。
- Script/State Outline: pending为每ID集合、error为每ID消息Map；set先检查当前请求和有效会话；await session.protect→api.setBookmark→核对返回ID和值→onConfirmed；失败只写error，finally清pending。当前页面回调同时更新F08和已打开详情的bool；切换路由重新GET，不创建浏览器业务库。重复点击只保留一个用户请求，不排队、不切换成功前bool；用户再次主动点击才重试。
- Style Outline: 原型bookmark圆形边框与图标、drawer secondary pill；mobile触控≥44；pending/失败不靠颜色区分，焦点ring稳定，不因重绘丢焦点。
- Visual / UX Checks: 列表与drawer同条目状态一致；失败明确未保存且保持原状态；图片失败期间文字、原文和收藏仍可达；不用toast代替持久错误区域。
- UI/E2E Lifecycle and Evidence: business-flow L-B；正常页面选择原未收藏真实标题，列表收藏→详情核对→浏览器关闭重开正常登录回看→取消→重开核对；014再核对收藏页。真实503须授权隔离服务真实存储故障，先正常登录再故障，恢复后页面主动重试；禁止修改API/DB内容或请求拦截。真实403不能安全触发时保留BLOCKED。清理必须恢复原收藏bool、网络和服务、关闭tab并退出，不取消客户原收藏。

### Visual Evidence Manifest — frontend-013

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BOOKMARK-CONFIRM | R-D card控件＋R-P/R-S | N/A VS-001 | R-D/R-P/R-S hash | card/drawer已收藏 | 原型tokens/R-F；Auto Layout N/A | `/`（详情可开） | 服务端确认/pending/取消 | 1440×900 | 1 | zh-CN | light | F-REAL；记录原bool和实际ID | `.fp-execute/visual/frontend-013/BOOKMARK-CONFIRM/reference.png` | `.fp-execute/visual/frontend-013/BOOKMARK-CONFIRM/current.png` | missing diff：按共同bookmark控件/确认状态复核 | None | 圆形图标/pressed和可见文案一致，失败前不提前改bool | CLI visual frontend-013/BOOKMARK-CONFIRM | core visual | PENDING |
| BOOKMARK-FAIL | R-M控件＋R-S失败规则 | N/A VS-001 | R-M/R-S hash | mobile收藏失败 | 原型tokens/R-F；Auto Layout N/A | `/` | 真实503/403、恢复主动重试 | 390×844 | 1 | zh-CN | light | F-REAL＋授权F-FAIL | `.fp-execute/visual/frontend-013/BOOKMARK-FAIL/reference.png` | `.fp-execute/visual/frontend-013/BOOKMARK-FAIL/current.png` | missing diff：按原状态/失败消息规则复核 | None | ≥44目标、原bool不变、错误可感知且不挡标题/焦点 | CLI visual frontend-013/BOOKMARK-FAIL | core visual | PENDING |
| BOOKMARK-IMAGEFAIL | R-M无图/控件＋R-S | N/A VS-001 | R-M/R-S hash | 图失败仍收藏 | 原型tokens/R-F；Auto Layout N/A | `/`（详情） | 真实图失败、业务API正常 | 390×844 | 1 | zh-CN | light | F-REAL＋第三方真实失败，本站在线 | `.fp-execute/visual/frontend-013/BOOKMARK-IMAGEFAIL/reference.png` | `.fp-execute/visual/frontend-013/BOOKMARK-IMAGEFAIL/current.png` | missing diff：按图失败文字和控件独立可用复核 | None | 图片失败不覆盖收藏/原文，确认反馈仍可见 | CLI visual frontend-013/BOOKMARK-IMAGEFAIL | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-013

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-013 | BOOKMARK-CONFIRM | 提案6；D-017/D-036；确认、单飞、列表/详情一致、浏览器重开持久、取消不删资讯 | business-flow | Visual BOOKMARK-CONFIRM route | REQUIRED | L-B；真实PUT/DELETE与重开页面持久结果；Mocked Core API:false；UI恢复原bool | `.fp-execute/e2e/frontend-013/BOOKMARK-CONFIRM/coverage-matrix.md` | BLOCKED：未执行；unit不能代替持久证据 |
| frontend-013 | BOOKMARK-FAIL | 提案6；401/403/503、保留原状态、不重放、恢复后用户重试 | business-flow | Visual BOOKMARK-FAIL route | REQUIRED | L-B；真实存储/权限故障；Mocked Core API:false；恢复环境并UI清理 | `.fp-execute/e2e/frontend-013/BOOKMARK-FAIL/coverage-matrix.md` | BLOCKED：真实安全503/403条件尚无；不可伪造请求/DB |
| frontend-013 | BOOKMARK-IMAGEFAIL | 提案5/6；真实第三方图失效不阻断收藏和原文 | business-flow | Visual BOOKMARK-IMAGEFAIL route | REQUIRED | L-B；真实图故障与本站写确认；Mocked Core API:false；取消新增收藏/恢复网络 | `.fp-execute/e2e/frontend-013/BOOKMARK-IMAGEFAIL/coverage-matrix.md` | BLOCKED：需要本站在线的真实图故障，不mock第三方 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/bookmarks/bookmarks.spec.ts tests/unit/features/headlines/source-image.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in BOOKMARK-CONFIRM BOOKMARK-FAIL BOOKMARK-IMAGEFAIL; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-013 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-013 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-013 --case "$c" --phase e2e || exit 1
done
```
- Expected: 独立视觉和真实持久／失败／清理均通过；unit补测返回ID不符、并发重复、重登不重放、同ID多入口，所有未实测分支保持BLOCKED。自审不复制快照、不写localStorage，确认边界说明与行为一致。

**Step 5: Commit**
```bash
git add frontend/src/features/bookmarks/components/BookmarkButton.vue frontend/src/features/bookmarks/bookmarks.ts frontend/src/features/headlines/components/HeadlineCard.vue frontend/src/features/headlines/components/DetailDrawer.vue frontend/src/features/headlines/views/WorkspaceView.vue frontend/tests/unit/features/bookmarks/bookmarks.spec.ts frontend/tests/browser/cases/bookmarks.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: synchronize only server confirmed bookmark results"
```

- [ ] **Task frontend-014: 建设服务器收藏页、独立排序和安全取消回看**

**Files:**
- Create: `frontend/src/features/bookmarks/views/FavoritesView.vue`、`frontend/tests/unit/features/bookmarks/favorites.spec.ts`、`frontend/tests/browser/cases/favorites.mjs`。
- Extend planned: `frontend/src/app/router.ts`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: FAVORITES-LIST、FAVORITES-EMPTY 双表。

**Reasoning:**
- 提案6/D-031/D-036 的收藏是同条目引用、按收藏时间排序，不是当前浏览器集合；取消不删除资讯，同链接元信息更新后仍指向原ID。

**Depends on:** frontend-010, frontend-013, backend-014, backend-039

**Interfaces:**
- Consumes: [F08/F09/F10/F11/F12/F13/F14](<05-interfaces.md>)、I14 ArticlePage。
- Produces: `/favorites` 的真实 FavoritesView；复用全部卡片／详情／筛选，不创建第二套视觉组件。
- Contract checks: 只GET bookmarks且每条bookmarked=true；不依reported_date重排；不显示不存在的created_at字段；取消确认后重取页，末页收缩回上一页；失败不移除。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：FAVORITES-LIST/FAVORITES-EMPTY。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import FavoritesView from '../../src/views/FavoritesView.vue'
import { createApi } from '../../../../src/shared/api/client'
import { createSession } from '../../../../src/features/auth/session'
import { articleFixture, authFixture, filtersFixture } from './fixtures'

it('keeps server bookmark order instead of sorting by reported date', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  vi.spyOn(api, 'listBookmarks').mockResolvedValue({ items: [
    articleFixture({ id: 2, bookmarked: true, reported_date: '2025-01-01' }),
    articleFixture({ id: 1, bookmarked: true, reported_date: '2026-01-01' })
  ], total: 2, page: 1, page_size: 20 })
  const session = createSession(api)
  await session.login('unit-only')
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/favorites', component: FavoritesView }] })
  await router.push('/favorites'); await router.isReady()
  const wrapper = mount(FavoritesView, { props: { api, session }, global: { plugins: [router] } })
  await flushPromises()
  expect(wrapper.findAll('[data-article-id]').map(n => n.attributes('data-article-id'))).toEqual(['2', '1'])
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/bookmarks/favorites.spec.ts`
- Expected: FavoritesView 不存在。

**Step 3: Write minimal implementation**
- Template Outline: FavoritesView props api/session，router为该页面绑定runtime实例；复用AppShell/SearchFilters/HeadlineList/DetailDrawer/BookmarkButton。h1“我的收藏”，排序说明“最近收藏”；真实空集合和筛选后空各有不同提示，可正常返回全部阅读。
- Script/State Outline: F08 bookmarkedOnly=true，F05 URL；详情使用同GET article；收藏确认callback更新已挂载bool，取消成功再reload当前页，total收缩时明确回上一有效页；保存失败保留卡和提示，不删除Article、不复制快照。
- Style Outline: R-D/R-M收藏入口与共用标题卡层级；空状态用既有h2/text/button，不加新大图或未获批装饰组件。
- Visual / UX Checks: 收藏与首页样式一致，最近收藏顺序文案正确，取消时焦点保留至相邻条目／结果标题；空收藏无假计数。
- UI/E2E Lifecycle and Evidence: business-flow L-B；页面收藏真实条目→收藏页核对ID/bool→正常浏览器重开登录→回看→详情／首页同状态→取消→确认原资讯仍可读；真实元信息更新仅用获准来源的实际再次更新，不改库/seed，尚未发生则相关覆盖BLOCKED。空收藏用原本无收藏的获准真实测试环境，不为测试取消客户历史收藏。cleanup恢复原bool和条件，正常退出。

### Visual Evidence Manifest — frontend-014

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FAVORITES-LIST | R-D/R-M共用卡＋R-S | N/A VS-001 | R-D/R-M/R-S hash | 收藏列表/最近收藏 | 原型tokens/R-F；Auto Layout N/A | `/favorites` | UI真实收藏后的列表/详情/取消 | 1440×900 | 1 | zh-CN | light | F-REAL；原bool、ID及UI操作顺序 | `.fp-execute/visual/frontend-014/FAVORITES-LIST/reference.png` | `.fp-execute/visual/frontend-014/FAVORITES-LIST/current.png` | missing diff：内容不同，按共享卡/状态规范复核 | None | 标题卡与首页同字阶；最近收藏文案、选中导航、取消焦点可见 | CLI visual frontend-014/FAVORITES-LIST | core visual | PENDING |
| FAVORITES-EMPTY | R-M控件＋R-S收藏空 | N/A VS-001 | R-M/R-S hash | mobile真空收藏/筛选空 | 原型tokens/R-F；Auto Layout N/A | `/favorites` | 真实无收藏/取消末条后空 | 390×844 | 1 | zh-CN | light | 原本空收藏真实环境；无seed/删除客户收藏 | `.fp-execute/visual/frontend-014/FAVORITES-EMPTY/reference.png` | `.fp-execute/visual/frontend-014/FAVORITES-EMPTY/current.png` | missing diff：按空态/导航规则独立复核 | None | 空态有返回全部/清筛选，44px可达，无假卡/假成功 | CLI visual frontend-014/FAVORITES-EMPTY | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-014

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-014 | FAVORITES-LIST | 提案6；D-031/D-036；三入口、收藏顺序/翻页/筛选、元信息跟随、重开、取消不删条目 | business-flow | Visual FAVORITES-LIST route | REQUIRED | L-B；真实UI写入/查询/重开结果；Mocked Core API:false；UI恢复原bool | `.fp-execute/e2e/frontend-014/FAVORITES-LIST/coverage-matrix.md` | BLOCKED：未执行；真实元信息更新若未发生保持该分支BLOCKED |
| frontend-014 | FAVORITES-EMPTY | R-S收藏真空/筛选空、取消末条/末页、失败仍在、返回全部 | business-flow | Visual FAVORITES-EMPTY route | REQUIRED | L-B；真实空/取消结果；Mocked Core API:false；不动客户原收藏，退出 | `.fp-execute/e2e/frontend-014/FAVORITES-EMPTY/coverage-matrix.md` | BLOCKED：需原本空收藏的真实测试环境和运行证据 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/features/bookmarks/favorites.spec.ts tests/unit/features/bookmarks/bookmarks.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in FAVORITES-LIST FAVORITES-EMPTY; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-014 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-014 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-014 --case "$c" --phase e2e || exit 1
done
```
- Expected: 独立视觉及真实三入口持久／排序／清理通过；unit补测末页收缩、503不移卡、空条件区别、同ID更新和原资讯仍在。自审组件复用、无第二份业务存储和不存在字段，注释说明取消不是删除条目。

**Step 5: Commit**
```bash
git add frontend/src/features/bookmarks/views/FavoritesView.vue frontend/src/app/router.ts frontend/tests/unit/features/bookmarks/favorites.spec.ts frontend/tests/browser/cases/favorites.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: add persistent server ordered favorites view"
```
