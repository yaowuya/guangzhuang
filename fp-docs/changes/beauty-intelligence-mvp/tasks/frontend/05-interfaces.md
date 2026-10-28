## 2. Frontend Interface and Visual Contract

这是本端调用、组件、状态和样式的唯一详细 owner。后端 DTO／HTTP 字段不在本文件复制，以[最终后端账本](<../backend/05-interfaces.md#http-字段和返回状态>)为准。任务内 Interfaces 引用下列 F 编号；任务内 case 双表是各 case 的唯一详细 owner。

| Contract | Owner Task | Exact shape / behavior | Consumers | Verification |
| --- | --- | --- | --- | --- |
| F01 工程入口 | frontend-001 | Vue3/TS/Vite/Router；package `type:'module'`，`base:'/'`、`build.outDir:'dist'`；最小App只有RouterView；check-artifact输出静态asset图hash作为build identity；无原型import、业务mock或dev proxy | backend-039、全部前端 | bootstrap spec、build、check-artifact |
| F02 来源冻结 | frontend-002 | `source-map.json` 含 [R-P/R-D/R-T/R-M/R-S/R-F](<01-context.md#12-已读来源冻结事实>)路径/hash/区域/允许内容删减；`check-visual-sources.mjs` 读取字节校验；来源改变必须失效相关视觉 review | 全部 UI case | visual-source spec、source-check |
| F03 同源 HTTP | frontend-003 | `createApi(fetcher=globalThis.fetch)` 返回精确命名方法；`ApiError(status,code,message,request_id)`；仅相对 `/api/`，`credentials:'same-origin'`，JSON，AbortSignal；不自动重试写 | F04/F08/F11/F13/F15/F16 | api-client spec |
| F04 会话 | frontend-004 | `createSession(api)`：`auth` ref 为 AuthOut 或 null，`status` 为 unknown/loading/authenticated/anonymous/expired；`ensure/login/logout/protect/clear`；CSRF 仅内存，单个 ensure promise 去重；runtime.ts 单例 api/session | 路由和全部受保护 composable | session spec |
| F05 URL | frontend-005 | `decodeQuery(URLSearchParams)`→`{ok:true,value:ArticleQuery}` 或 `{ok:false,message}`；`encodeQuery`、`changeFilters`、`safeReturn`；重复单值／非法日期／页码不悄悄放宽为全部 | route、列表、筛选、收藏 | query spec |
| F06 登录和路由 | frontend-006 | `/login`、`/`、`/favorites`；`createAppRouter(session)`；守卫检查服务器；LoginView props `{session,returnTo}`，成功 emits `authenticated`；WorkspaceView 先为真实路由容器 | shell、收藏、E2E | login spec、AUTH cases |
| F07 壳和导航 | frontend-007 | AppShell props `{title,subtitle}`，slots search/default/status；NavMenu props `{activeCategory,routeName}` emits `navigate`；IconButton `{label,pressed?,disabled?}` emits click；StatusNotice `{kind,message}` 原生 role | 009～017 | navigation spec、NAV cases |
| F08 读取状态 | frontend-008 | `useHeadlines({api,session,query,bookmarkedOnly})`→`page,filters,loading,refreshing,error,load,reload,applyBookmark`；AbortController+generation 丢弃旧结果，dispose abort | Workspace/Favorites | headlines spec |
| F09 列表／分页 | frontend-009 | HeadlineCard `{article,featured}` emits `open(id)`；HeadlineList `{page,loading,error}` emits open/page/retry；PaginationControls `{page,pageSize,total,disabled}` emits page；不嵌套按钮，不客户端再排序 | Workspace、Favorites、drawer | headline-list spec、LIST cases |
| F10 筛选 | frontend-010 | SearchFilters `{query,options,error?}` emits `change(patch),reset`；q 仅标题／来源，category/region/product_type/date_from/date_to；变更 page=1；动态地区/品类只从 FiltersOut 取得 | Workspace/Favorites | filters spec、FILTER cases |
| F11 详情 | frontend-011 | `useDrawer()` 维护 selectedId/opener/scroll；DetailDrawer `{id,api,session}` emits close；受保护 GET 详情，原生 dialog、aria-labelledby；关闭恢复原 opener 和 scroll；历史返回先关闭面板，不增加 API query 字段 | Workspace/Favorites | detail spec、DETAIL cases |
| F12 图片／外链 | frontend-012 | SourceImage `{url,credit,title}`；`safeExternalUrl(value,kind)` 仅无凭据 http(s) 原文／HTTPS 图片，拒绝控制符和危险协议；new tab + noopener noreferrer；img referrerpolicy=no-referrer | card/drawer | source-image spec、MEDIA cases |
| F13 收藏确认 | frontend-013 | `createBookmarks({api,session,onConfirmed})`→`pending,error,set(article,value)`；按 ID 单飞，确认后广播已挂载列表／drawer 的 bool；不建第二份持久业务库；BookmarkButton `{article,pending,error}` emits set | card/drawer/Favorites | bookmarks spec、BOOKMARK cases |
| F14 收藏页 | frontend-014 | FavoritesView 使用 F08 bookmarkedOnly=true 与 F10；GET bookmarks 服务器顺序；取消成功后重新取当前页，必要时回上一有效页；未确认前不移除 | Router/AppShell | favorites spec、FAVORITES cases |
| F15 来源 | frontend-015 | `useSources({api,session})`→`items,loading,error,load`；SourceStatus/SourceRow 只读；精确五站六入口，不把 partial 网站汇总当本入口 enabled | Workspace/UpdateStatus | sources spec、SOURCE cases |
| F16 更新 | frontend-016 | `useUpdateJob({api,session,onFinished})`→`job,loading,submitting,error,refresh,retry,loadCurrent,stop`；current null 单独显示；pending/running 用完成后 setTimeout 2 s 查询，单飞、最多观察 600 s 后提示仍在进行且停止，卸载/隐藏/终态/401 停止；恢复可见先 current | Workspace/SourceStatus | update-job spec、UPDATE cases |
| F17 响应式／焦点 | frontend-017 | `useOverlay()` 管理 nav/detail/sources 互斥，关闭/路由变更/卸载恢复 inert、body overflow 和焦点；不留下隐藏可聚焦区域 | 全部 UI | accessibility spec、ACCESS cases |
| F18 证据只读校验 | frontend-018 | check-delivery 校验显式 case 注册、原始来源hash、分离的 reference/current、review 身份／环境和必需阶段；不自动计算视觉 PASS，不运行浏览器写操作 | 发布 | delivery-gate spec、独立 review |
| F19 联验 | frontend-019 | CLI 用正常UI串行执行真实更新→标题→筛选/详情→收藏→浏览器重开/授权进程重启→回看→取消→清理；`validateRelease(observations)`从实际证据验证真实持久和清理，报告绑定同一release/build/env；批准隔离演练另标variant | 最终前端交付 | release-gate spec、LIVE cases |

### 2.1 Component tree and template outline

```text
App -> RouterView
  LoginView -> 原生 form/password/button + StatusNotice（007 后复用）
  WorkspaceView/FavoritesView -> AppShell
    NavMenu + search slot: SearchFilters
    status slot: UpdateStatus + StatusNotice
    HeadlineList -> HeadlineCard -> SourceImage + BookmarkButton
    PaginationControls
    DetailDrawer -> 标题/元信息/SourceImage/原文 a/BookmarkButton
    SourceStatus -> SourceRow[] + UpdateStatus
```

组件名和原型区域映射来自[确认设计组件表](<../../design/frontend.md#ui-组件树与-figma-解析映射>)。不得复制演示切换器、实图样例按钮、中文要点、事实格或多来源事件区。登录和来源面板是新增完整画面，不假称原型已经逐像素覆盖。

### 2.2 State/API/interaction design

| Method in createApi | Backend owner / contract | Call rules |
| --- | --- | --- |
| `login(password)`、`getSession()`、`logout(csrf)` | [I08 / backend-008](<../backend/05-interfaces.md#http-字段和返回状态>) | login POST 精确 `{password}` 且无 CSRF；session GET；logout POST `{}` 带 CSRF；Cookie 由浏览器管理，不手写 Origin/Cookie |
| `listArticles(query,signal)`、`getArticle(id,signal)`、`getFilters(signal)` | [I12 / backend-012](<../backend/30-reading-tasks.md#L190-L249>) | 请求字段只有 ArticleQuery；detail 正整数；400 invalid_filter 与 404 不是空库 |
| `listBookmarks(query,signal)`、`setBookmark(id,value,csrf)` | [I14 / backend-014](<../backend/30-reading-tasks.md#L314-L369>) | true→PUT `{}`；false→DELETE 无 body；只接受 BookmarkOut 的 article_id/bookmarked 确认；503 保留上次成功状态 |
| `listSources(signal)` | [I16 / backend-016](<../backend/40-source-security-tasks.md#L62-L116>) | 读取 `{items:SourceOut[]}`；许可状态、enabled、last_success_at/last_error 各有标签；不提供编辑 |
| `createJob(csrf)`、`retryJob(id,csrf)`、`getCurrentJob(signal)`、`getJob(id,signal)` | [I25 / backend-025](<../backend/50-job-tasks.md#L126-L184>) | refresh body 仅 `{trigger:'refresh'}`；retry POST `{}`；200 reused 和 202 new 都成功，保留 reused；current 读取 `{job:null}`；409 原 code 可感知；不自行采集 |
| 构建目录 | [I39 / backend-039](<../backend/70-release-tasks.md#L61-L129>) | Caddy 读 frontend/dist，`/api` 不改写；真实 UI 不以 Vite dev server 代替同域 HTTPS |

TS 类型逐字转换后端账本所有消费 DTO，包括可空字段、完整 SourceRef、EnqueueOut/CurrentJobOut；不把 `partial` 加到入口许可枚举。七 CategoryCode 使用账本固定顺序；`__uncategorized__` 和 `__unknown__` 只是查询哨兵。动态 region/product_type 不发明枚举。

URL 只保存读取条件和 page/page_size，不保存 CSRF、口令、收藏集合或任务写队列。q 原样编码交服务器做 NFKC/casefold 字面匹配；百分号和下划线不由前端改成通配符。筛选控件仅接受已返回选项，手改 URL 的动态未知值由后端 400 解释，不自动悄悄重置成全部。

列表首次加载与同条件后台刷新分开；后台更新、读失败和任务失败不抹已确认数据。新条件请求须表明正在载入该条件，不把旧条件结果冒充新匹配。详情关闭不重新制造列表；刷新后的收藏 bool 以服务器为准。跨标签页不本地复制业务数据，回到可见页重新读取。

### 2.3 Style and responsive design

| Surface / region | Concrete source-backed target |
| --- | --- |
| Tokens | [原型:12–13](<../../prototype.html#L12-L13>)：ground/raised `#fff`，surface `#f4f6f5`，chrome `#f7f8f7`，border `#e3e7e4`，text `#1f201d`，muted `#5e655f`，accent `#1b6e66`，negative `#b42318`；gap 16 px；body 14 px；h1 24 px；focus outline 3 px |
| Desktop | [原型:14–19](<../../prototype.html#L14-L19>)：导航 224 px，topbar 72 px，内容 max 1100 px，画布 padding 32 px，12 列 16 px gap；卡首条 span8、其它 span4，2 条 span6、1 条全宽；不填回已取消内容 |
| Tablet ≤1100 px | [原型:21](<../../prototype.html#L21>)：导航折叠为 240 px 面板，topbar 64 px，正文 padding 28/24 px；首卡全宽、其余双列；隐藏导航 inert |
| Mobile ≤640 px | [原型:22、29、33](<../../prototype.html#L22-L33>)：390/360 px 验证；topbar 56 px、正文 padding 20/16 px；同一个搜索框进入正常文档流，不绝对定位遮挡标题；单列卡，圆角 18 px；触控目标至少 44 px |
| Controls and drawer | 原型 pill 控件约 36～38 px，卡圆角 22 px；[原型:19](<../../prototype.html#L19>) drawer 右侧 max590 px/100dvh；手机全宽；新表单沿用同字体、边框和留白，不伪造完整参考图 |
| Font / motion | R-F 本地字体与 OFL 一起交付；中文 Microsoft YaHei/PingFang SC；不引用 CDN；`prefers-reduced-motion:reduce` 禁过渡和动画。无新增 dark 主题范围 |

### 2.4 Visual and UX checks

- 保留 R-D/R-T/R-M 中导航、主面、控件、字阶和卡片主次；title-only 允许自然收缩。首次为空、无匹配、收藏空、读失败和更新失败各有语义，不借“本次无新增”掩盖空库或失败。
- 标题、日期未披露、来源、原文入口、收藏和错误可见。长外语标题换行不截断核心内容；无图／外链失败不放无关图，不妨碍文字与收藏。
- 页面以 keyboard 完成登录、导航、筛选、分页、drawer、收藏、刷新和重试；Tab 不进入 inert 内容，Escape 关闭当前层，焦点恢复；mobile 不横向溢出，200% 缩放仍可达。
- 400、401、403、404、409、429、503 按服务器真实语义展示；重试必须是用户主动动作，会话恢复后不重放写入。来源 pending/restricted/partial 与运行 failed 不混淆。

### 2.5 Visual Evidence Manifest conventions

每个 UI 任务的表按模板完整 21 列记录唯一 case。下列约定定义表中的稳定引用，不形成第二份 case 表：

- `R-*` 的文件、revision/hash 由[来源表](<01-context.md#12-已读来源冻结事实>)唯一持有；revision 单元格引用源 key，表示冻结该 hash，不表示 Figma revision。Figma node 全部 `N/A (VS-001)`。variables 是真实 CSS tokens；Auto Layout=N/A；assets=R-F，业务图不能当参考资产。
- `F-REAL`：页面从获准真实更新返回的公开非敏感条目；默认按真实首页服务端顺序选首个未收藏条目，分页用同次结果前两条，有图case仅选该结果中首个实际获准image_url非空条目。执行前正常UI选定并记录实际article ID/title/source/link/date和原bool，冻结这些身份与条件，不注入数据；条件不足即BLOCKED，不能硬编码样本顶替。相同运行比较复用冻结条目；若真实更新改变样本则重新capture/review。`F-EMPTY`：授权隔离真实环境尚无记录的实际状态；`F-FAIL`：授权实际服务／权限故障。它们是稳定选择规则，不是 fixture 文件；条件未获得就 BLOCKED。
- 原图 reference 只从获批静态图转换／裁切。共同区域：R-D 导航 `[0,0,224,900]`、toolbar `[278,190,1100,80]`、卡 `[278,282,728,420]`；R-M 搜索/筛选 `[16,166,358,132]`、卡 `[16,311,358,511]`。新登录、来源和删减后的 drawer 使用这些原子控件裁片＋R-S 规则独立审查，明确不是全画面逐像素参考。reference 不可由目标运行页、unit fixture 或新造 mock 画面生成。
- 每 case 标准目录 `.fp-execute/visual/<task>/<case>/` 内的 manifest 记录来源hash、current build/env/time、viewport/DPR/locale/theme 和样本；reference.png 为已批准静态来源，current.png 为真实目标 route 截图；可选 diff 缺失写 `missing diff` 和区域比较理由，不能掩盖 source/current 缺失。表中的路径均从当前 change 根解析。
- 视觉命令精确展开为 `"$NODE_EXE" frontend/scripts/browser-case.mjs --task <task-id> --case <case-id> --phase source` 和同参 `--phase visual`，工作目录仓库根；每个任务 Step 4 给出所属 case 命令。source 阶段只读批准静态源，visual 阶段只捕获 current，不批准自己。表中 `CLI visual TASK/CASE` 即这两条精确映射，不是另一个工具。
- 独立、新鲜、只读 visual reviewer 只能写本 case 的 `review.md`，不能改实现、reference/current、manifest 或 lifecycle。它核对现有三类 artifact 和真实 route/state，输出恰 `VISUAL_REVIEW_PASS` / `CANNOT_VERIFY` / `FAIL`。owner 根据合格 review 记录阶段。不同内容不定义全局像素阈值；按 case 的几何／字体／可达性和明确允许差异审查，不能声称标题版和旧摘要卡像素一致。

### 2.6 UI/E2E Delivery Contract conventions

本端所有 product UI case 均 interactive 或 business-flow，没有为了省 E2E 伪装 static-only 的 case。001～005、008、018 是工程／纯状态／只读审查任务，不呈现产品 UI，不创建虚构 UI case；其 unit 测试不满足任何所需 E2E。

`L-B`（business-flow）和 `L-I`（interactive）的精确阶段均为 `SOURCE_READY -> STATIC_UI_READY -> VISUAL_REVIEW_PASS -> INTERACTION_READY -> FRONTEND_E2E_PASS -> FINAL_REVIEW -> ARCHIVE`。SOURCE/STATIC 由 owner 的 visual manifest 和 current build 证明，VISUAL 由独立 review.md 证明；INTERACTION/E2E 由独立渠道 e2e manifest/run/coverage-matrix 证明。任务内 lifecycle 字段用 L-B/L-I 指向本定义，不复制视觉字段。

`Mocked Core API: false` 对全部 REQUIRED case 生效。business-flow 还需浏览器实际同源请求记录和持久化／权限结果；禁止密码、Cookie、CSRF 和 storageState 落证据。实时网络 metadata 的只读观察可用，request context/direct API write 不可代替 UI。浏览器交互记录与 current 截图分开。

每次 E2E 必存 Executed command、Environment identity、Destination、Start/End、Attempts、Test IDs、Artifacts、Coverage matrix reference、Cleanup。每对 task/case 唯一 canonical `.fp-execute/e2e/<task>/<case>/coverage-matrix.md`，逐项覆盖正常／分支、校验边界、加载空错重试、权限隔离、持久和导航、竞态、分页筛选排序兼容；状态只能 `covered | N/A | BLOCKED`。计划时均为 BLOCKED（未实现／未执行），不是 covered；不适用的细分条件需真实依据，必需 E2E 永不 N/A。

清理：先从页面记录受测真实条目原收藏 bool；优先选择未收藏条目，通过页面取消本次新增引用并验证列表／详情／收藏；原来已收藏时恢复原值，不取消客户原收藏。不删除真实来源条目或伪造任务结果；更新产生的真实 job/article 保留，记录 ID 和经批准的保留理由。真实服务故障／重启须维护者授权并恢复，记检查结果；cleanup 未完成阻塞。登录会话最终正常退出，所有浏览器 session 在 finally close。

失败规则：视觉 FAIL 仅退到 STATIC_UI_READY；交互/E2E FAIL 仅退到 INTERACTION_READY；来源或当前画面变化使旧视觉结论失效。核心缺口、mock 违规或清理失败最多 3 次诊断尝试，第三次仍失败即 BLOCKED，不第四次重跑，不记 review debt、N/A、PASS_WITH_NOTES 或人工豁免。

### 2.7 准确命令与单元测试约定

执行时先 `load_workspace_dependencies`，把实际返回的绝对路径绑定为 `NODE_EXE`、`PNPM_JS`、`PYTHON_EXE`（在 bash 中用正斜线的绝对路径）；后文变量只引用这些已解析值。运行前仅在当前子进程环境设置 `export PATH="$(dirname "$NODE_EXE"):$PATH"`，确保 pnpm scripts 中的 node 仍是该 bundled Node，不修改系统/用户全局 PATH 或工具配置。不得用 bare node/pnpm 偷换 runtime。当前不执行下面任何安装／工程／浏览器命令。

```bash
# 仅未来 frontend-001、用户确认计划后；cwd=仓库根。
"$NODE_EXE" "$PNPM_JS" --dir frontend add vue@3 vue-router@4
"$NODE_EXE" "$PNPM_JS" --dir frontend add -D typescript@5 vite@7 @vitejs/plugin-vue@6 vue-tsc@3 vitest@4 @vue/test-utils@2 jsdom@27 @types/node@24
"$NODE_EXE" "$PNPM_JS" --dir frontend run test:unit -- tests/unit/bootstrap.spec.ts
"$NODE_EXE" "$PNPM_JS" --dir frontend run typecheck
"$NODE_EXE" "$PNPM_JS" --dir frontend run build
"$NODE_EXE" "$PNPM_JS" --dir frontend run check:artifact
```

上述 major 是拟选兼容范围，不声称已安装的精确 patch；执行时记录解析版本并提交唯一 frontend lockfile。安装失败回报原因，不静默改 major 或加浏览器依赖。`packageManager` 固定 `pnpm@11.28.5`。不使用 `pnpm dlx`／`npx` 临时下载 browser runner。

package scripts 精确目标：`test:unit="vitest run"`；`typecheck="vue-tsc --noEmit -p tsconfig.app.json"`；`build="vue-tsc --noEmit -p tsconfig.app.json && vite build"`；`check:artifact="node scripts/check-artifact.mjs"`；`source-check="node scripts/check-visual-sources.mjs"`；`check:delivery="node scripts/check-delivery.mjs"`（分别由 001/002/018 引入）。pnpm 脚本内部 node 由已选 bundled Node 的目录进入该子进程 PATH；前置脚本检查 process.version，版本不符失败，不修改全局 PATH 配置。

Vitest 显式 include `tests/unit/**/*.spec.ts`、environment jsdom、setup `tests/unit/setup.ts`、restoreMocks/clearMocks=true；测试文件显式 import describe/it/expect/vi。Typecheck 的 app include `src/**/*.ts,src/**/*.vue,src/env.d.ts`，不把 mjs/browser 放入 app project。test fixture `articleFixture(overrides)`、`authFixture()`、`filtersFixture()`、`sourceFixture(overrides)`、`jobFixture(overrides)` 在 unit/fixtures.ts，字段符合后端 DTO，仅使用 `https://unit.example/` 和合成标题。unit 中 `vi.fn`/fake timers 可以隔离，browser 目录禁止导入它们。

浏览器封装的显式合同（006 实现）：命令 `--task ID --case ID --phase source|visual|e2e --environment LABEL --origin HTTPS_ORIGIN`；origin/environment 来自已确认输入或 `BI_ORIGIN/BI_ENVIRONMENT`，缺失即非零。CLI entry、版本和 schema 必须在执行环境从已安装 package/`--help` 重新发现，并用 bundled Node 调用；不得提交本机绝对路径、临时下载或假定规划时安装位置。局部配置显式使用 `--config frontend/tests/browser/cli.config.json`：

```json
{"browser":{"browserName":"chromium","isolated":true,"launchOptions":{"channel":"chrome","headless":false},"contextOptions":{"viewport":{"width":1440,"height":900},"deviceScaleFactor":1,"locale":"zh-CN","colorScheme":"light","reducedMotion":"reduce"}}}
```

case 按表用既有CLI resize或page.setViewportSize改变尺寸，不改DPR/locale；不使用persistent profile/storageState，不修改全局配置。source阶段通过 `PYTHON_EXE` 调用既有Pillow，先验源hash，再把批准JPG转换/裁切为PNG，不能拿目标浏览器截图充reference，也不新增图像依赖。

规划时已核对已安装 CLI 的 run-code 安全边界；执行时须从当前 package 文档/`--help` 重新确认：隔离上下文没有process/require，不能假设process.env可传口令。默认使用可见Chrome：操作者只在正常页面原生密码框输入真实口令；脚本继续触发正常submit并自动断言真实登录、权限和业务结果。这只是凭据安全输入，不是人工批准/豁免E2E。禁真口令进入CLI fill/run-code参数、源码/临时文件、日志、artifact；认证阶段不录trace/HAR/body，仅在密码框清空后保存脱敏状态。没有可见输入能力且没有另经核验批准的安全通道时BLOCKED，不新建secret桥接服务或安装runner。

每case独立命名session，默认动作等待60s，更新最多观察600s；凭据输入单独有界等待并如实计入run，超时BLOCKED；串行业务写入、finally close。发现不支持的配置/Chrome能力则BLOCKED，不暗装别的runner。
