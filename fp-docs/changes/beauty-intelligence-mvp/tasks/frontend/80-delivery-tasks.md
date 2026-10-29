## 独立视觉审查和真实业务联验任务

- [ ] **Task frontend-018: 校验证据分离并进行独立只读视觉总复核**

**Files:**
- Create: `frontend/scripts/check-delivery.mjs`、`frontend/tests/unit/app/delivery-gate.spec.ts`。
- Extend planned: `frontend/package.json`。
- Future review output: `fp-docs/changes/beauty-intelligence-mvp/.fp-execute/visual/reviews/frontend-018/review.md`。各UI case的review.md仍由原owner的独立审查阶段持有，不搬迁case或checkbox。

**Reasoning:**
- VS-001仅改来源类型，不取消独立review。此任务防止把旧原型自检、作者截图或不完整E2E当完成；它消费全部已实现UI case，不创造第二套visual manifest。

**Depends on:** frontend-017

**Interfaces:**
- Consumes: [F02/F18、独立review与生命周期](<05-interfaces.md#25-visual-evidence-manifest-conventions>)和各任务原case双表。
- Produces: check-delivery只读校验命令、独立总review；不能自动批准视觉，也不改实现或source/current。
- Contract checks: 单case唯一owner；批准来源hash/图像内容与current分离；缺current/reference、过期build、作者自审、必需E2E缺失或cleanup未完成均非零；无Figma不冒充Figma-only通过。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。UI/E2E Applicability：不适用，本任务是只读审查／门禁工具，没有新增产品UI。复核原UI owner的所有case，不把缺其E2E改N/A。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { validateDelivery } from '../../scripts/check-delivery.mjs'

it('rejects runtime-as-reference even when a report claims all stages passed', () => {
  const record = { taskId: 'frontend-006', caseId: 'AUTH-BASE',
    approvedSourceKind: 'target-runtime', referencePresent: true, currentPresent: true,
    visualResult: 'VISUAL_REVIEW_PASS', e2eResult: 'PASS',
    mockedCoreApi: false, cleanup: 'complete' }
  expect(() => validateDelivery([record])).toThrow(/approved source/)
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/app/delivery-gate.spec.ts`
- Expected: check-delivery/validateDelivery 尚不存在；不得把检查器拒绝现阶段未生成证据误报为测试通过。

**Step 3: Write minimal implementation**
- Template Outline: 无产品模板；审查输出引用原task/case，不再写新case矩阵。
- Script/State Outline: validateDelivery先检查获批source kind与来源分离，再校验必填字段／阶段／独立review者和case完整集合。CLI读取真实磁盘manifest、PNG签名、source hash、build/env和run/coverage文件，拒绝空数组all()通过、重复case、未执行/skip/MockedCoreAPI非false、缺cleanup。注册表只提供显式清单和module path，不因少注册一个case就缩小应验集合；必需case集合与本计划owner表比对。018默认校验006～017全部UI case；019注册LIVE-D/M后 `--include-release` 一并强制校验。检查器不比较像素后自动签发PASS，不联网、不发业务请求、不自动改lifecycle。
- Style Outline: 不适用。reviewer按原case的规则/区域比较，不新增全局pixel阈值或新设计。
- Visual / UX Checks: 施工者先完成并提交当前build的source/current证据准备。随后使用全新独立只读reviewer；该阶段只能写此总review，不能修改工具、实现、source-evidence、current或任何lifecycle。逐case读manifest/reference/current/可选diff并确认真实route/state，尤其审登录、来源、新标题版drawer的规范与共同控件，而不是伪造完整逐像素参考。输出恰VISUAL_REVIEW_PASS/CANNOT_VERIFY/FAIL及逐case理由。
- UI/E2E Lifecycle and Evidence: 本任务没有新case，不自造SOURCE_READY；原case的视觉/真实E2E阶段与owner保持唯一。CANNOT_VERIFY阻塞；FAIL回原owner的STATIC_UI_READY修复，重拍和独立复核；三次仍失败BLOCKED，不第四次，不记Review Debt。

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/app/delivery-gate.spec.ts`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run source-check`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run check:delivery`。
- Expected: 单元反例覆盖runtime reference、缺图、伪review、错hash/env/build、孤立case、无matrix、mock/skip、清理失败；实际check仅在全部真实原case证据齐全才退出0。独立review只读完成后才可声称视觉总审通过，不把脚本退出0当独立review。
- 自审：审查与实现身份独立，来源异常不豁免；必要说明清楚界定检查器能证明的结构事实和不能证明的视觉判断。本轮无任何已执行review。

**Step 5: Commit**
```bash
git add frontend/scripts/check-delivery.mjs frontend/tests/unit/app/delivery-gate.spec.ts frontend/package.json
git commit -m "test: gate delivery on separated sources and independent visual review"
```

- [ ] **Task frontend-019: 在目标同域环境完成正常页面真实业务、重启持久与清理联验**

**Files:**
- Create: `frontend/tests/browser/cases/release.mjs`、`frontend/tests/unit/app/release-gate.spec.ts`。
- Extend planned: `frontend/scripts/check-delivery.mjs`、`frontend/tests/browser/case-registry.mjs`、`frontend/tests/browser/support.mjs`。
- Future evidence: LIVE-D、LIVE-M 双表；`fp-docs/changes/beauty-intelligence-mvp/.fp-execute/frontend-release.md`。

**Reasoning:**
- P-013/D-026/D-028 的正式交付必须有真实许可来源、真实标题、正常UI收藏和重启后回看。后端API验收只提供前提，不替代浏览器；截图也不能替代持久化或清理证据。

**Depends on:** frontend-017, frontend-018, backend-008, backend-012, backend-014, backend-016, backend-025, backend-039, backend-041

**Interfaces:**
- Consumes: [F01～F19](<05-interfaces.md>)和所有原case的覆盖矩阵；I08/I12/I14/I16/I25/I39/I41真实提供者。
- Produces: 同release/build/目标HTTPS的真实UI联验与最终前端报告；LIVE-D/M唯一case owner为019，不修改其他task完成状态。
- Contract checks: Mocked Core API:false；通过页面登录／刷新／收藏／取消；真实API和持久结果；至少一个获准入口目标环境成功；重启证据真实；无第四次重试；全部来源/当前图和独立review完整。

**Capability / Preservation Ownership:**
- FIGCAP: None；PRES: None。Browser replay：LIVE-D/LIVE-M；不依赖backend-045，不制造前后端汇总环。

**Step 1: Write the failing test**
```ts
import { it, expect } from 'vitest'
import { validateRelease } from '../../scripts/check-delivery.mjs'

it('requires persistence and cleanup in addition to all real UI observations', () => {
  // UNIT_ONLY：这些合成值只测拒绝规则，绝不是正式执行证据。
  const complete = { environment: 'unit-target', origin: 'https://unit.example',
    sourcePermissionVerified: true, realSourceUpdated: true, uiLoginObserved: true,
    uiRefreshObserved: true, uiBookmarkObserved: true, browserReopened: true,
    serverRestartObserved: true, persistenceVerified: true, cleanupComplete: true,
    mockedCoreApi: false, requiredCasesComplete: true }
  expect(() => validateRelease(complete)).not.toThrow()
  expect(() => validateRelease({ ...complete, persistenceVerified: false })).toThrow(/persistence/)
  expect(() => validateRelease({ ...complete, cleanupComplete: false })).toThrow(/cleanup/)
})
```
**Step 2: Run test to verify it fails**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/app/release-gate.spec.ts`
- Expected: 018仅有validateDelivery，尚未导出validateRelease，测试因该专门门禁缺失失败；实现后两个负向断言分别验证持久和清理，不靠其它缺字段假RED。真实E2E初始运行：`"$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-019 --case LIVE-D --phase e2e`，缺实现/环境/独立review或真实条件必须非零/BLOCKED，不能skip冒充。

**Step 3: Write minimal implementation**
- Template Outline: 无新增产品画面，只使用已经建设的正常 `/login`、`/`、`/favorites`、详情和来源面板。不得为了E2E加隐藏按钮、测试登录、样本入口或业务写API。
- Script/State Outline: 在check-delivery中新增 `validateRelease(observations)`，校验同环境/HTTPS、真实许可与UI登录/刷新/收藏、浏览器和服务器重启、真实持久、清理、MockedCoreAPI=false及全部case完整。CLI必须从真实artifact/实际运行观察计算这些规范化字段，不能信任手填布尔值；unit合成对象仅测拒绝规则。release.mjs注册两个独立case并串行执行：①真实页面登录；②来源面板确认至少一个当前allowed+enabled入口和许可依据；③工作台点击刷新，观察真实job/entry终态和真实title/link；④正常页面七类/搜索/动态筛选/分页及详情/原文；⑤记录原收藏bool，选原未收藏真实条目，页面收藏，三个入口核对；⑥关闭浏览器重开、正常登录并回看；⑦获准维护窗口由操作者真实重启API/worker（不改DB/时钟/许可，不自动运行未经批准重启），从实际部署记录/进程重启时间/同目标env日志取得可复核观察，随后正常页面重开登录回看收藏与标题；⑧UI取消本次新增收藏并核对原资讯仍可读；⑨恢复原bool、关闭tab/面板、退出并close。若原条目原本已收藏则换未收藏样本，找不到时不破坏客户数据，保持BLOCKED。
- Real failure/coverage: 从各原case矩阵检查加载/空/错/重试、401/403、source状态、图失效/直链、任务终态/复用、持久和竞态均有真实证据。单元覆盖不能填covered；没有安全真实404/403/受限/部分失败等条件，保留对应BLOCKED并阻塞最终报告。生产不能安全触发时仅在明确授权、相同真实构建的隔离真实环境演练并精确标environment variant，绝不冒称生产已见；不能mock或写seed。
- Style Outline: 不新造样式；最终dist重新构建，与Caddy实际挂载及build identity一致。保存本地font与OFL，原型源码/数据/运行脚本不进dist；原业务图不内嵌或转存。
- Visual / UX Checks: LIVE-D/M按R-D/R-M和R-S独立审查最终真实画面；新画面仍按规则＋共同原子控件审，不声明不存在的逐像素参考。单独保存browser flow与current screenshot。
- UI/E2E Lifecycle and Evidence: business-flow，L-B完整阶段。环境身份、destination、start/end、attempts、test IDs、命令、artifacts、canonical矩阵、Mocked Core API:false、真实API/persistence/permission/cleanup逐项必填。维护重启需要可核实的实际观察，不凭手填passed；等待授权/真实样本/维护记录的时间不计成功。真实更新产生的job/article只保留并列出ID/许可与保留理由，不删除或倒写结果，收藏通过UI恢复。未cleanup即BLOCKED。

### Visual Evidence Manifest — frontend-019

| Case ID | Approved design source | Figma node | revision/time | Frame/variant | variables / Auto Layout / assets | Runtime route | Scenario/state | Viewport | DPR | Locale | Theme | Deterministic non-sensitive fixture | Reference path | Current path | Diff path / missing diff | Mask | Acceptance rule | Command/tool | Failure class | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LIVE-D | R-D＋R-P＋R-S | N/A VS-001 | R-D/R-P/R-S hash | 最终标题工作台/收藏 | 原型tokens/R-F；Auto Layout N/A | `/`、`/favorites` | 真实刷新/收藏/重启回看/取消 | 1440×900 | 1 | zh-CN | light | 本次UI真实刷新取得的公开title/link/ID与原bool | `.fp-execute/visual/frontend-019/LIVE-D/reference.png` | `.fp-execute/visual/frontend-019/LIVE-D/current.png` | missing diff：内容不同，按保留壳/字阶/控件和规范复核 | None | 224导航/1100主体/16gap、无旧分析区、全部业务反馈可读；独立review最终build | CLI visual frontend-019/LIVE-D | core visual | PENDING |
| LIVE-M | R-M＋R-P＋R-S | N/A VS-001 | R-M/R-P/R-S hash | 最终mobile闭环 | 原型tokens/R-F；Auto Layout N/A | `/login`、`/`、`/favorites` | 真实mobile刷新/详情/收藏/重开/清理 | 390×844 | 1 | zh-CN | light | 同目标环境真实title/link/ID，独立记录原bool | `.fp-execute/visual/frontend-019/LIVE-M/reference.png` | `.fp-execute/visual/frontend-019/LIVE-M/current.png` | missing diff：按单列/原子控件/规则复核 | None | 无横溢、44操作、搜索正常流、drawer全宽、来源可滚动、错误/清理可达 | CLI visual frontend-019/LIVE-M | core visual | PENDING |

### UI/E2E Delivery Contract — frontend-019

| Task ID | Case ID | Source-derived condition / requirement reference | UI Delivery Level | Runtime route reference / E2E route | E2E Applicability | Required lifecycle path / stage evidence | Coverage matrix | N/A / BLOCKED rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frontend-019 | LIVE-D | P-013/D-026/028/036；UI登录/真实刷新/title/link/三入口收藏/浏览器和进程重启持久/取消/清理 | business-flow | Visual LIVE-D route | REQUIRED | L-B；独立review＋真实业务run/维护观察/API与持久结果；Mocked Core API:false；UI恢复原bool/退出 | `.fp-execute/e2e/frontend-019/LIVE-D/coverage-matrix.md` | BLOCKED：云HTTPS、来源许可、真实数据、重启授权和全部证据尚未具备 |
| frontend-019 | LIVE-M | R-S mobile；目标环境完整正常UI业务/返回/图失败不阻读藏/清理 | business-flow | Visual LIVE-M route | REQUIRED | L-B；独立review＋真实mobile业务run；Mocked Core API:false；UI清理/关层tab/退出 | `.fp-execute/e2e/frontend-019/LIVE-M/coverage-matrix.md` | BLOCKED：未实现/未执行，不能用desktop或原型证据替代 |

**Step 4: Run test to verify it passes**
- Run: `"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run source-check`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run build`；`"$NODE_EXE" "$PNPM_JS" --dir frontend run check:artifact`。
```bash
for c in LIVE-D LIVE-M; do
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-019 --case "$c" --phase source || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-019 --case "$c" --phase visual || exit 1
  "$NODE_EXE" frontend/scripts/browser-case.mjs --task frontend-019 --case "$c" --phase e2e || exit 1
done
"$NODE_EXE" "$PNPM_JS" --dir frontend run check:delivery -- --include-release
```
- Expected: 每case先独立视觉放行，真实闭环／重启／清理和所有原case矩阵完整，且check:delivery退出0；最终报告同时记录已测与仍BLOCKED项，不把测试计划、skip、空库或第三次失败改PASS。最大3次，第四次禁止。
- 自审：工程规范、注释、无过度设计、字段/路径/版本、来源与当前图分离、无mock/no bypass、清理和未覆盖前提逐项检查。只有实际全通过才勾选019；frontend-019 当前仍未执行／未测试，不能从其它已完成任务推断。

**Step 5: Commit**
```bash
git add frontend/tests/browser/cases/release.mjs frontend/tests/unit/app/release-gate.spec.ts frontend/tests/browser/case-registry.mjs frontend/tests/browser/support.mjs
git commit -m "test: verify real ui persistence restart and cleanup delivery"
```
