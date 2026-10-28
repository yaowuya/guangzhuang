## 五站只读状态与更新任务交互

- [ ] **Task frontend-015: 展示五站六入口的独立许可与运行状态**

**Files:**
- Create: `frontend/src/components/SourceStatus.vue`、`frontend/src/components/SourceRow.vue`、`frontend/src/state/sources.ts`、`frontend/tests/unit/sources.spec.ts`、`frontend/tests/browser/cases/sources.mjs`。
- Extend planned: `frontend/src/views/WorkspaceView.vue`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: SOURCE-D、SOURCE-M 双表。

**Reasoning:**
- 提案2/D-013/D-014/D-035 要求五站作为目标清单而非全部接入声明，PR TIMES 两入口分别展示证据；网站 partial 不能放行 pending 入口。

**Depends on:** frontend-009, frontend-011, backend-016, backend-039

**Interfaces:**
- Consumes: [F07/F12/F15](<05-interfaces.md>)、[I16](<../backend/40-source-security-tasks.md#L62-L116>)。
- Produces: useSources、SourceStatus/SourceRow；工作台可开关只读面板。
- Contract checks: SourceOut网站 allowed/partial/pending/restricted 和 EntryOut入口 allowed/pending/restricted 区别；enabled、许可原因/依据、last_success_at、last_error 不互相替代；无source写操作。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：SOURCE-D/SOURCE-M。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SourceRow from '../../src/components/SourceRow.vue'
import { sourceFixture } from './fixtures'

it('does not present a pending entry as enabled because its site is partial', () => {
  const source = sourceFixture({ verification_status: 'partial', entries: [{
    id: 11, url: 'https://unit.example/list', kind: 'public_list',
    verification_status: 'pending', verification_reason: null,
    verification_reference: null, enabled: false, last_success_at: null, last_error: null }] })
  const wrapper = mount(SourceRow, { props: { source } })
  expect(wrapper.text()).toContain('待核验')
  expect(wrapper.text()).toContain('未启用')
  expect(wrapper.find('input, select').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('全部已接入')
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/sources.spec.ts`
- Expected: SourceRow 不存在。

**Step 3: Write minimal implementation**
- Template Outline: SourceStatus props items/loading/error，dialog或可关闭工作台面板→h2“来源状态”＋5站SourceRow；每站展开全部入口、URL/kind、许可状态／原因／依据、enabled、最后成功和最近访问错误。支持正常GET重试，不出现编辑、启停开关、审核或新增来源按钮。
- Script/State Outline: useSources 显式load，经session.protect；组件卸载取消GET，错误不造空成功；面板打开才加载。用 SourceOut.key 对照 prtimes/happi/qingyan/pbn/cosin，数量异常给契约错误，不填假站。verification_reference可为依据字符串，不强行当URL；仅安全http(s)才a，其余文本。最后成功UTC明确按北京时间展示标签，null写“尚无成功记录”，运行错误不改许可。
- Style Outline: 新来源完整画面按R-S设计和R-D/R-M的字体、边框、状态色、16px节奏；不是原型已画好的逐像素面板。长URL换行，mobile面板可滚动，close≥44px。
- Visual / UX Checks: 待核验/受限/部分允许/启用分别用可读文字；PR TIMES双入口分开；最后成功和错误并存；无“全球完整覆盖”“五站已成功”虚假结论。
- UI/E2E Lifecycle and Evidence: business-flow L-B；正常登录→工作台来源入口→五站六入口逐条核对实际API状态和安全依据→关闭恢复焦点。实际 pending/restricted/partial 以各入口真实核验结果为准，不修改配置/DB来制造许可；没有相应安全真实状态则该coverage BLOCKED。真实GET错误/恢复仍需授权服务条件。cleanup关面板/恢复服务/退出，无业务数据写入。

### Visual Evidence Manifest — frontend-015

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SOURCE-D | R-D控件＋R-S来源规则 | N/A VS-001 | R-D/R-S hash | 新来源面板/desktop | 原型tokens/R-F；Auto Layout N/A | `/`（来源面板） | 真实五站六入口/许可与运行区分 | 1440×900 | 1 | zh-CN | light | 实际SourceOut，非敏感依据/状态稳定记录 | `.fp-execute/visual/frontend-015/SOURCE-D/reference.png` | `.fp-execute/visual/frontend-015/SOURCE-D/current.png` | missing diff：无批准完整来源面板，原子控件＋规范复核 | None | 层级/字阶/间距沿用，许可/启用/错误独立标签，完整新增画面独立复核 | CLI visual frontend-015/SOURCE-D | core visual | PENDING |
| SOURCE-M | R-M控件＋R-S来源规则 | N/A VS-001 | R-M/R-S hash | 新来源面板/mobile | 原型tokens/R-F；Auto Layout N/A | `/`（来源面板） | 长依据/未知成功时间/GET错误 | 390×844 | 1 | zh-CN | light | 实际SourceOut/获准真实读错F-FAIL | `.fp-execute/visual/frontend-015/SOURCE-M/reference.png` | `.fp-execute/visual/frontend-015/SOURCE-M/current.png` | missing diff：按共同控件与可达规则复核 | None | URL换行、滚动可达、44关闭、错误不覆盖最后成功值 | CLI visual frontend-015/SOURCE-M | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-015

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-015 | SOURCE-D | 提案2；D-013/014/035；五站六入口、许可/启用/运行独立、无编辑 | business-flow | Visual SOURCE-D route | REQUIRED | L-B；真实来源GET和权限run；Mocked Core API:false；关面板/退出 | `.fp-execute/e2e/frontend-015/SOURCE-D/coverage-matrix.md` | BLOCKED：尚无页面与逐入口真实核验状态证据 |
| frontend-015 | SOURCE-M | R-S mobile/来源；loading/error/retry、长依据与关闭焦点 | business-flow | Visual SOURCE-M route | REQUIRED | L-B；真实mobile/读错重试run；Mocked Core API:false；恢复故障/退出 | `.fp-execute/e2e/frontend-015/SOURCE-M/coverage-matrix.md` | BLOCKED：缺安全实际故障与mobile运行证据 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/sources.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in SOURCE-D SOURCE-M; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-015 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-015 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-015 --case "$c" --phase e2e || exit 1
done
```
- Expected: 独立视觉先通过，真实只读状态/权限/重试及cleanup齐全；unit覆盖所有许可枚举不算真实coverage。自审不把网站国别当市场、不从面板启用来源，组件职责说明区分许可与网络错误。

**Step 5: Commit**
```bash
git add frontend/src/components/SourceStatus.vue frontend/src/components/SourceRow.vue frontend/src/state/sources.ts frontend/src/views/WorkspaceView.vue frontend/tests/unit/sources.spec.ts frontend/tests/browser/cases/sources.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: show readonly per entry source permission and runtime status"
```

- [ ] **Task frontend-016: 页面刷新、持久任务观察和只重试失败入口**

**Files:**
- Create: `frontend/src/components/UpdateStatus.vue`、`frontend/src/state/update-job.ts`、`frontend/tests/unit/update-job.spec.ts`、`frontend/tests/browser/cases/updates.mjs`。
- Extend planned: `frontend/src/views/WorkspaceView.vue`、`frontend/src/components/SourceStatus.vue`、`frontend/tests/browser/case-registry.mjs`。
- Future evidence: UPDATE-ACTIVE、UPDATE-RESULT、UPDATE-NOENTRY、UPDATE-RETRY 双表。

**Reasoning:**
- 提案2/D-023/D-025/D-030 需要即时任务ID、重开可见、已有标题可读、部分失败/全失败/无新增分别反馈；浏览器不采集、不调度和不自行排队。

**Depends on:** frontend-014, frontend-015, backend-025, backend-039

**Interfaces:**
- Consumes: [F03/F04/F08/F15/F16](<05-interfaces.md>)、[I25](<../backend/50-job-tasks.md#L126-L184>)。
- Produces: useUpdateJob、UpdateStatus；工作台主动刷新和来源面板失败入口重试。
- Contract checks: POST body精确refresh，重试只job id且不发送入口列表；200 reused/202 new同样消费；current null；六JobState/五EntryResultState；计数不自增；结束／卸载停止轮询。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：UPDATE-ACTIVE/RESULT/NOENTRY/RETRY。

**Step 1: Write the failing test**
```ts
import { it, expect, vi } from 'vitest'
import { createApi } from '../../src/api/client'
import { createSession } from '../../src/state/session'
import { useUpdateJob } from '../../src/state/update-job'
import { authFixture } from './fixtures'

it('represents no current job honestly without starting a poll', async () => {
  vi.useFakeTimers()
  try {
    const api = createApi(vi.fn<typeof fetch>())
    vi.spyOn(api, 'login').mockResolvedValue(authFixture())
    vi.spyOn(api, 'getCurrentJob').mockResolvedValue({ job: null })
    const session = createSession(api)
    await session.login('unit-only')
    const state = useUpdateJob({ api, session, onFinished: vi.fn() })
    await state.loadCurrent()
    expect(state.job.value).toBeNull()
    expect(vi.getTimerCount()).toBe(0)
    state.stop()
  } finally { vi.useRealTimers() }
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/update-job.spec.ts`
- Expected: useUpdateJob 尚不存在。

**Step 3: Write minimal implementation**
- Template Outline: 工作台刷新button＋UpdateStatus显示ID、trigger标签、state、每入口结果/计数/error、最后成功线索；SourceStatus共享同一job状态／retry按钮，不创建第二条轮询链。无记录写“尚无更新记录”，无可用来源409写真实原因和来源入口，不伪装成功。
- Script/State Outline: mount/重新可见先current；pending/running单飞地await GET后setTimeout 2s，终态/401/卸载/隐藏停止并abort；最多观察600s后仅提示仍在运行、由用户再次查看，不把服务器任务改failed。按钮submitting防双击，多tab并发由后端reused处理，展示同任务ID。终态一次调用onFinished使当前列表／sources正常GET重取；不清旧标题或收藏。retry只原failed/interrupted且当前eligible交集，选择由后端权威决定；无候选409和job不存在404如实反馈，不自己改成功结果。trigger只显示schedule/catchup/refresh/retry，UI不提交schedule/catchup。
- State labels: succeeded且count_added/count_updated均0显示“本次无新增，已有内容保留”；有updated单独说明，partial/failed/interrupted不得标全部成功。last_success_at只从来源入口读取，null不造时间；时间显示北京时间并保留服务器UTC供证据引用。静态“每日07:30 北京时间”是计划频率，不是某次实际已执行证明。
- Style Outline: 原型status-line、secondary/text-button和字体层级；mobile状态纵向、长error换行、44px操作；状态不依赖颜色，spinner尊重reduced-motion。
- Visual / UX Checks: 更新期间原列表可读；真实active、partial、failed、interrupted、succeeded/no-new、null和409不混淆；重试不显示已成功入口为待重试。
- UI/E2E Lifecycle and Evidence: business-flow L-B；正常页面刷新真实许可源，观察任务ID及终态；两真实浏览器正常点击验证reused，关浏览器再登录current仍可见。部分失败/中断/重试/无来源需真实许可/服务条件及维护授权；不改源许可、job响应、系统时间或DB来凑状态。不能安全得到的分支BLOCKED。清理通过UI恢复受测收藏，真实更新产生article/job不删除，记录ID和获准保留理由；故障/维护恢复并退出。

### Visual Evidence Manifest — frontend-016

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UPDATE-ACTIVE | R-D刷新/状态原子＋R-S | N/A VS-001 | R-D/R-S hash | active/reused | 原型tokens/R-F；Auto Layout N/A | `/` | 页面真实刷新pending/running、重开 | 1440×900 | 1 | zh-CN | light | 获准真实source/job ID；无fixture | `.fp-execute/visual/frontend-016/UPDATE-ACTIVE/reference.png` | `.fp-execute/visual/frontend-016/UPDATE-ACTIVE/current.png` | missing diff：按原子控件/状态规则复核 | None | 刷新和任务ID清楚、旧列表仍可读、无假进度百分比 | CLI visual frontend-016/UPDATE-ACTIVE | core visual | PENDING |
| UPDATE-RESULT | R-M状态原子＋R-S | N/A VS-001 | R-M/R-S hash | 终态/无新增 | 原型tokens/R-F；Auto Layout N/A | `/` | 真实succeeded/partial/failed/interrupted/零新增 | 390×844 | 1 | zh-CN | light | 实际job/entry结果和计数 | `.fp-execute/visual/frontend-016/UPDATE-RESULT/reference.png` | `.fp-execute/visual/frontend-016/UPDATE-RESULT/current.png` | missing diff：新状态按规范逐分支复核 | None | 状态纵排、44操作、部分失败非全成功，无新增非空库 | CLI visual frontend-016/UPDATE-RESULT | core visual | PENDING |
| UPDATE-NOENTRY | R-D控件＋R-S未启用规则 | N/A VS-001 | R-D/R-S hash | current null/409 | 原型tokens/R-F；Auto Layout N/A | `/`（来源面板） | 真无记录/无可启用来源 | 1440×900 | 1 | zh-CN | light | 获准新真实环境/真实未核验入口 | `.fp-execute/visual/frontend-016/UPDATE-NOENTRY/reference.png` | `.fp-execute/visual/frontend-016/UPDATE-NOENTRY/current.png` | missing diff：规则/共同控件独立复核 | None | 明确尚无记录/没有已启用入口，不填假成功时间 | CLI visual frontend-016/UPDATE-NOENTRY | core visual | PENDING |
| UPDATE-RETRY | R-M控件＋R-S重试规则 | N/A VS-001 | R-M/R-S hash | 失败入口重试 | 原型tokens/R-F；Auto Layout N/A | `/`（来源面板） | 实际失败/中断入口重试、409/404 | 390×844 | 1 | zh-CN | light | 原真实job＋当前真实eligible状态 | `.fp-execute/visual/frontend-016/UPDATE-RETRY/reference.png` | `.fp-execute/visual/frontend-016/UPDATE-RETRY/current.png` | missing diff：按结果/重试规则复核 | None | 原成功项不列重试、错误原因清楚，旧内容不抹除 | CLI visual frontend-016/UPDATE-RETRY | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-016

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-016 | UPDATE-ACTIVE | 提案2；D-023/025；正常UI刷新、pending/running、200复用/202新建、重开current、不阻读 | business-flow | Visual UPDATE-ACTIVE route | REQUIRED | L-B；真实job/entry请求结果＋持久重开；Mocked Core API:false；记录保留job/article并退出 | `.fp-execute/e2e/frontend-016/UPDATE-ACTIVE/coverage-matrix.md` | BLOCKED：未执行真实来源更新/并发复用 |
| frontend-016 | UPDATE-RESULT | 提案2；终态全覆盖、计数、无新增、成功保留、停止轮询 | business-flow | Visual UPDATE-RESULT route | REQUIRED | L-B；真实终态和请求停止证据；Mocked Core API:false；恢复维护条件/退出 | `.fp-execute/e2e/frontend-016/UPDATE-RESULT/coverage-matrix.md` | BLOCKED：需真实终态/零新增条件，不mock |
| frontend-016 | UPDATE-NOENTRY | D-014/025；current null、409 no_enabled_sources、无伪成功 | business-flow | Visual UPDATE-NOENTRY route | REQUIRED | L-B；真实新环境/无来源拒绝；Mocked Core API:false；无伪数据清理 | `.fp-execute/e2e/frontend-016/UPDATE-NOENTRY/coverage-matrix.md` | BLOCKED：真实无记录/未启用环境未准备 |
| frontend-016 | UPDATE-RETRY | D-023/030；仅原失败/中断且仍可用、无候选409、404/401、重试不重采成功 | business-flow | Visual UPDATE-RETRY route | REQUIRED | L-B；真实retry及入口结果对照；Mocked Core API:false；恢复故障/保留job清单/退出 | `.fp-execute/e2e/frontend-016/UPDATE-RETRY/coverage-matrix.md` | BLOCKED：需实际失败/中断及可安全拒绝条件，不能改DB/许可 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/update-job.spec.ts tests/unit/sources.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`。
```bash
for c in UPDATE-ACTIVE UPDATE-RESULT UPDATE-NOENTRY UPDATE-RETRY; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-016 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-016 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-016 --case "$c" --phase e2e || exit 1
done
```
- Expected: 独立视觉及真实业务E2E通过；unit用fake timers补测2s单飞、600s停止、dispose/hidden/401/终态停止、旧请求迟到、200/202、各终态/null/409，不计真实分支覆盖。自审无前端采集/日程/假时间/写队列，轮询与恢复边界注释准确。

**Step 5: Commit**
```bash
git add frontend/src/components/UpdateStatus.vue frontend/src/state/update-job.ts frontend/src/views/WorkspaceView.vue frontend/src/components/SourceStatus.vue frontend/tests/unit/update-job.spec.ts frontend/tests/browser/cases/updates.mjs frontend/tests/browser/case-registry.mjs
git commit -m "feat: observe persistent update jobs and retry only failed entries"
```
