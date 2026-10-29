## Coverage Matrix

本片只映射覆盖，不拥有任务checkbox、HTTP DTO、视觉manifest或UI/E2E详细契约。本文生成时19任务全部未完成；当前完成度从唯一owner checkbox与双端overview派生。33个UI case仍没有生产证据时保持Visual=PENDING、必需E2E保持BLOCKED；这里不因unit或原型验证生成PASS/covered事实。

### 需求与设计覆盖

| Source | Requirement / capability / preservation / visual boundary | Tasks | Verification |
| --- | --- | --- | --- |
| [提案P-012、设计D-005](<../../proposal.md#handoff-decision-ledger>) | 无生产前端；Vue3/TS/Vite/Router；最小dist独立供Caddy | frontend-001 | bootstrap.spec、typecheck/build/check:artifact；最小产物不等于产品 |
| [D-001/D-020、前端Visual Source](<../../design/frontend.md#visual-source>)、2026-10-27“前端使用原型” | VS-001获批原型/静态图/规范基准；不要求Figma，仅覆盖来源类型 | frontend-002、007、018 | source-check、原task全部case独立review；禁止runtime作reference |
| [提案1、D-003/D-017/D-032](<../../design/backend.md#decision-ledger>) | 首登/退出/服务器会话、CSRF、失效安全返回、不自动重放写 | frontend-003、004、005、006 | api-client/session/query/login.spec；AUTH三个case真实权限结果 |
| [提案1/3、D-011/D-025](<../../proposal.md#what-changes>) | 全部/收藏/七类、未分类仍可读；无品牌国别市场推断 | frontend-005、007、009、010 | query/navigation/headline-list/filters.spec；NAV/LIST/FILTER |
| [提案3/4、D-009/D-024/D-037](<../../design/frontend.md#状态管理>) | 标题/来源检索、动态region/product_type、未知哨兵、日期含界、页码与URL；接受位移 | frontend-003、005、008、009、010 | 客户端/查询/竞态单元；真实FILTER/分页/回退matrix，不seed凑数据 |
| [提案4、D-025](<../../design/frontend.md#页面视图>) | 详情侧栏、原文主动new tab、焦点/scroll/筛选返回 | frontend-011、012、017 | DETAIL/MEDIA/ACCESS；真实同条目/外链/关闭/back |
| [提案5、D-026](<../../proposal.md#5-外链展示图片不建设图片存储服务>) | 第三方直链、许可与署名、无图/失效/拒绝/离线，不代理转存，文字/收藏可用 | frontend-012、013、019 | source-image.spec；MEDIA三case、BOOKMARK-IMAGEFAIL、LIVE-M；实际网络metadata |
| [提案6、D-031/D-036](<../../design/backend.md#decision-ledger>) | 服务器收藏、三入口bool、单飞/失败保留、收藏时间序、取消不删条目、元信息跟随 | frontend-013、014、019 | bookmarks/favorites.spec；BOOKMARK/FAVORITES/LIVE真实持久和UI清理 |
| [提案2、D-013/D-014/D-035](<../../design/backend.md#后端模块设计>) | 五站六入口、PR TIMES双入口、只读许可/启用/访问错误独立，不伪称全部接入 | frontend-015 | sources.spec和SOURCE-D/M；真实逐入口状态；无编辑API/控件 |
| [提案2、D-023/D-030](<../../design/frontend.md#状态管理>) | UI刷新/重试、任务ID/current、200/202、终态/无新增/null/409、旧列表可读、停止轮询 | frontend-016 | update-job.spec；UPDATE四case真实job/entry与请求停止；不替后端调度 |
| [前端Visual Checks、验证方案](<../../design/frontend.md#visual-checks>) | desktop1440/tablet768/mobile390/360、44px、全键盘/缩放/reduced-motion、浮层清理 | frontend-007、009、010、011、015、017 | 对应viewport case与ACCESS-KBD/MOBILE；独立视觉与真实交互两渠道 |
| [提案Out of Scope](<../../proposal.md#out-of-scope>)、D-008/D-010 | 不导入原型虚构数据/正文/摘要/成分/研究/上市提炼/事件归并/模型/收费管理 | frontend-001、002、003、009、011、018、019 | 字段/模板/构建扫描及真实UI核查；不把取消内容列为像素差异缺陷 |
| [D-018/D-021/D-028](<../../design/backend.md#decision-ledger>) | 同域HTTPS、Caddy真实dist、至少一个许可来源目标环境真实更新、最终持久/清理 | frontend-001、006、009、019 | I39/I41提供者；LIVE-D/M和全部原case，不依赖backend-045 |
| [前端工程质量/风险](<../../design/frontend.md#风险迁移发布回滚与监控>) | 小组件/局部状态、必要职责和原因说明，无多余抽象，保留失败阻塞 | 全部task，018/019收口 | 每task Step4自审；源码实际diff/测试/注释一致后才完成 |
| Figma能力映射 | 无Figma输入；FIGCAP不适用，不创建虚构ledger | 无 | VS-001下仍逐case独立视觉审查，不声称Figma-only门禁通过 |
| 旧生产行为保留 | 无旧生产UI/API；PRES不适用；原型localStorage不迁移 | 无 | 没有虚构before/after replay；已有原型不修改 |

### Case owner 与未来证据导航

下表只导航唯一owner。Visual manifest/reference/current/可选diff位于原task双表中的精确visual目录；独立review.md同目录。浏览器manifest/run/artifacts位于下列coverage-matrix的同目录。全部是未来拟生成路径，本轮没有写入任何execution evidence。

| Task ID | Case ID | Unique owner | Future canonical coverage matrix |
| --- | --- | --- | --- |
| frontend-006 | AUTH-BASE | [access任务](<20-access-navigation-tasks.md#visual-evidence-manifest--frontend-006>) | `.fp-execute/e2e/frontend-006/AUTH-BASE/coverage-matrix.md` |
| frontend-006 | AUTH-FAIL | [access任务](<20-access-navigation-tasks.md#visual-evidence-manifest--frontend-006>) | `.fp-execute/e2e/frontend-006/AUTH-FAIL/coverage-matrix.md` |
| frontend-006 | AUTH-EXPIRED | [access任务](<20-access-navigation-tasks.md#visual-evidence-manifest--frontend-006>) | `.fp-execute/e2e/frontend-006/AUTH-EXPIRED/coverage-matrix.md` |
| frontend-007 | NAV-D | [导航任务](<20-access-navigation-tasks.md#visual-evidence-manifest--frontend-007>) | `.fp-execute/e2e/frontend-007/NAV-D/coverage-matrix.md` |
| frontend-007 | NAV-M | [导航任务](<20-access-navigation-tasks.md#visual-evidence-manifest--frontend-007>) | `.fp-execute/e2e/frontend-007/NAV-M/coverage-matrix.md` |
| frontend-009 | LIST-D | [读取任务](<30-reading-tasks.md#visual-evidence-manifest--frontend-009>) | `.fp-execute/e2e/frontend-009/LIST-D/coverage-matrix.md` |
| frontend-009 | LIST-T | [读取任务](<30-reading-tasks.md#visual-evidence-manifest--frontend-009>) | `.fp-execute/e2e/frontend-009/LIST-T/coverage-matrix.md` |
| frontend-009 | LIST-M | [读取任务](<30-reading-tasks.md#visual-evidence-manifest--frontend-009>) | `.fp-execute/e2e/frontend-009/LIST-M/coverage-matrix.md` |
| frontend-009 | LIST-EMPTY | [读取任务](<30-reading-tasks.md#visual-evidence-manifest--frontend-009>) | `.fp-execute/e2e/frontend-009/LIST-EMPTY/coverage-matrix.md` |
| frontend-009 | LIST-READFAIL | [读取任务](<30-reading-tasks.md#visual-evidence-manifest--frontend-009>) | `.fp-execute/e2e/frontend-009/LIST-READFAIL/coverage-matrix.md` |
| frontend-010 | FILTER-COMBINED | [筛选任务](<30-reading-tasks.md#visual-evidence-manifest--frontend-010>) | `.fp-execute/e2e/frontend-010/FILTER-COMBINED/coverage-matrix.md` |
| frontend-010 | FILTER-INVALID | [筛选任务](<30-reading-tasks.md#visual-evidence-manifest--frontend-010>) | `.fp-execute/e2e/frontend-010/FILTER-INVALID/coverage-matrix.md` |
| frontend-011 | DETAIL-D | [详情任务](<40-detail-media-tasks.md#visual-evidence-manifest--frontend-011>) | `.fp-execute/e2e/frontend-011/DETAIL-D/coverage-matrix.md` |
| frontend-011 | DETAIL-M | [详情任务](<40-detail-media-tasks.md#visual-evidence-manifest--frontend-011>) | `.fp-execute/e2e/frontend-011/DETAIL-M/coverage-matrix.md` |
| frontend-011 | DETAIL-FAIL | [详情任务](<40-detail-media-tasks.md#visual-evidence-manifest--frontend-011>) | `.fp-execute/e2e/frontend-011/DETAIL-FAIL/coverage-matrix.md` |
| frontend-012 | MEDIA-ALLOWED | [媒体任务](<40-detail-media-tasks.md#visual-evidence-manifest--frontend-012>) | `.fp-execute/e2e/frontend-012/MEDIA-ALLOWED/coverage-matrix.md` |
| frontend-012 | MEDIA-ABSENT | [媒体任务](<40-detail-media-tasks.md#visual-evidence-manifest--frontend-012>) | `.fp-execute/e2e/frontend-012/MEDIA-ABSENT/coverage-matrix.md` |
| frontend-012 | MEDIA-FAIL | [媒体任务](<40-detail-media-tasks.md#visual-evidence-manifest--frontend-012>) | `.fp-execute/e2e/frontend-012/MEDIA-FAIL/coverage-matrix.md` |
| frontend-013 | BOOKMARK-CONFIRM | [收藏写任务](<50-bookmark-tasks.md#visual-evidence-manifest--frontend-013>) | `.fp-execute/e2e/frontend-013/BOOKMARK-CONFIRM/coverage-matrix.md` |
| frontend-013 | BOOKMARK-FAIL | [收藏写任务](<50-bookmark-tasks.md#visual-evidence-manifest--frontend-013>) | `.fp-execute/e2e/frontend-013/BOOKMARK-FAIL/coverage-matrix.md` |
| frontend-013 | BOOKMARK-IMAGEFAIL | [收藏写任务](<50-bookmark-tasks.md#visual-evidence-manifest--frontend-013>) | `.fp-execute/e2e/frontend-013/BOOKMARK-IMAGEFAIL/coverage-matrix.md` |
| frontend-014 | FAVORITES-LIST | [收藏页任务](<50-bookmark-tasks.md#visual-evidence-manifest--frontend-014>) | `.fp-execute/e2e/frontend-014/FAVORITES-LIST/coverage-matrix.md` |
| frontend-014 | FAVORITES-EMPTY | [收藏页任务](<50-bookmark-tasks.md#visual-evidence-manifest--frontend-014>) | `.fp-execute/e2e/frontend-014/FAVORITES-EMPTY/coverage-matrix.md` |
| frontend-015 | SOURCE-D | [来源任务](<60-source-update-tasks.md#visual-evidence-manifest--frontend-015>) | `.fp-execute/e2e/frontend-015/SOURCE-D/coverage-matrix.md` |
| frontend-015 | SOURCE-M | [来源任务](<60-source-update-tasks.md#visual-evidence-manifest--frontend-015>) | `.fp-execute/e2e/frontend-015/SOURCE-M/coverage-matrix.md` |
| frontend-016 | UPDATE-ACTIVE | [更新任务](<60-source-update-tasks.md#visual-evidence-manifest--frontend-016>) | `.fp-execute/e2e/frontend-016/UPDATE-ACTIVE/coverage-matrix.md` |
| frontend-016 | UPDATE-RESULT | [更新任务](<60-source-update-tasks.md#visual-evidence-manifest--frontend-016>) | `.fp-execute/e2e/frontend-016/UPDATE-RESULT/coverage-matrix.md` |
| frontend-016 | UPDATE-NOENTRY | [更新任务](<60-source-update-tasks.md#visual-evidence-manifest--frontend-016>) | `.fp-execute/e2e/frontend-016/UPDATE-NOENTRY/coverage-matrix.md` |
| frontend-016 | UPDATE-RETRY | [更新任务](<60-source-update-tasks.md#visual-evidence-manifest--frontend-016>) | `.fp-execute/e2e/frontend-016/UPDATE-RETRY/coverage-matrix.md` |
| frontend-017 | ACCESS-KBD | [响应式任务](<70-responsive-tasks.md#visual-evidence-manifest--frontend-017>) | `.fp-execute/e2e/frontend-017/ACCESS-KBD/coverage-matrix.md` |
| frontend-017 | ACCESS-MOBILE | [响应式任务](<70-responsive-tasks.md#visual-evidence-manifest--frontend-017>) | `.fp-execute/e2e/frontend-017/ACCESS-MOBILE/coverage-matrix.md` |
| frontend-019 | LIVE-D | [联验任务](<80-delivery-tasks.md#visual-evidence-manifest--frontend-019>) | `.fp-execute/e2e/frontend-019/LIVE-D/coverage-matrix.md` |
| frontend-019 | LIVE-M | [联验任务](<80-delivery-tasks.md#visual-evidence-manifest--frontend-019>) | `.fp-execute/e2e/frontend-019/LIVE-M/coverage-matrix.md` |

001～005、008、018共7个工程/纯状态/审查任务不创建虚构UI case。其余12个UI task拥有33个case，其中2个interactive（NAV-D/M）、31个business-flow，全部E2E REQUIRED。没有为了避开必需E2E而定义static-only或N/A的case。

### 仍未覆盖的真实前提

1. 目标云资源、精确HTTPS域名、DNS/证书、Caddy实际dist和合法测试账号尚未取得真实部署证据；本地包、脚本和构建是否存在以当前源码/锁文件/progress为准，不能替代同域云验收。
2. 至少一个入口必须得到真实自动读取/标题保存许可并在目标环境成功更新。图许可可为false，但真实有图/拒绝/失效case不能因此假PASS；未获所需真实样本的分支保持BLOCKED，不拿历史图或fixture顶替。
3. 七类、未知值、日期含界、多条分页、真实同链接元信息变化等条件必须来自真实来源观察。样本缺失不seed、不修改真实标题/日期/分类；相关coverage明确BLOCKED。
4. 真空库/空收藏/无任务/无启用来源需要获准全新隔离真实环境，不清生产库或客户历史收藏；记录实际environment variant，不能与目标生产环境混淆。
5. 真实401/403/429/404/503、部分失败/全失败/中断、重试候选变化、第三方图片拒绝等需安全实际条件和授权。没有安全触发途径则BLOCKED，不用route/intercept或API/DB写入替代正常被测UI。
6. 浏览器重开和获准API/worker进程重启后的真实持久回看、200%浏览器缩放、最终UI清理都未执行；主代理的about:blank smoke不覆盖这些行为。独立视觉review尚未进行。

### 计划自审与主调度边界

- 上游small XOR、旧路径缺失、standalone原型XOR和本端split入口已核验；没有写small plan、后端plan、overview、上游设计/提案/PRD、普通计划、settings/intel、插件、生产文件或execution evidence。
- 静态计划校验：12份Markdown、19个连续唯一task、33对case双表；完整逻辑计划写后约1,800行/15万字符，单片最大289行/17,289字符，支持写前选split的量级判断且均在硬限内。两端实际64节点owner依赖图（含主代理已添加的frontend-001→backend-039）无环；manifest无漏片/双形式，全部Files在结构表，链接/anchor和表列数一致。此处记录规划生成时的TS/bash/JSON语法校验；当前单元、类型、构建、视觉或E2E结果只能由Git与progress中的实际命令证明，语法校验不能替代。
- 唯一[manifest](<00-index.md#fragment-manifest>)按context→interface→tasks→coverage排序；01拥有约束/结构，05拥有详细前端契约，各task片拥有唯一task/case，90仅映射。ID连续frontend-001～019；当前checkbox状态以owner文件与overview为准，不在本映射重复。
- 后端引用仅008/012/014/016/025/039/041，均已从[最终账本](<../backend/05-interfaces.md>)、[manifest](<../backend/00-index.md>)和精确owner文件核对。字段/枚举/NULL/200/202/400/401/403/404/409/429/503消费一致；无从普通计划猜字段。
- 001独立产出frontend/dist，不依赖任何后端。主代理负责给backend-039添加frontend-001前置，方向为frontend-001→backend-039；本端只声明后续消费边。009显式等待backend-041的既有真实来源前提，不靠未来016刷新UI回头解锁自身。019不依赖backend-045。主代理基于两端owner graph生成overview，本子代理不写overview。
- 33对case的Visual/UIE2E双表、source/current/diff路径、mask/acceptance/tool/failureclass、canonical matrix、生命周期、Mocked Core API:false和清理均逐case登记。Reference只来自批准静态源或规范的共同控件，新增画面不伪造全像素参照；未生成证据无PASS。
- 所有task包含完整Files/Reasoning/Depends on/Interfaces、Template/Script/Style/VisualChecks及五步TDD、准确RED/GREEN命令、自审和Commit步骤；是否已执行以owner checkbox、Git和progress为准。静态计划校验不等于工程单元/构建/视觉/业务E2E通过。
