# Execution Progress

Plan files:
- Backend canonical: [tasks/backend/00-index.md](<../tasks/backend/00-index.md>)，split。
- Backend ordered fragments: `01-context.md` → `05-interfaces.md` → `10-foundation-tasks.md` → `20-auth-tasks.md` → `30-reading-tasks.md` → `40-source-security-tasks.md` → `45-ingestion-tasks.md` → `50-job-tasks.md` → `55-schedule-backup-tasks.md` → `60-source-verification-tasks.md` → `70-release-tasks.md` → `80-live-acceptance-tasks.md` → `90-coverage.md`，均相对上述 backend 目录。
- Frontend canonical: [tasks/frontend/00-index.md](<../tasks/frontend/00-index.md>)，split。
- Frontend ordered fragments: `01-context.md` → `05-interfaces.md` → `10-foundation-tasks.md` → `20-access-navigation-tasks.md` → `30-reading-tasks.md` → `40-detail-media-tasks.md` → `50-bookmark-tasks.md` → `60-source-update-tasks.md` → `70-responsive-tasks.md` → `80-delivery-tasks.md` → `90-coverage.md`，均相对上述 frontend 目录。
- Derived overview: [tasks/00-overview.md](<../tasks/00-overview.md>)。

Base SHA: `27c016f62984c3e1e9732f08201b92f24d4da9ca`

## Execution authorization

- 用户对规范任务计划的写后确认原文：“确认”，对应进入 `fp-execute` 的阶段询问。
- 模式：`full`，当前上下文直接执行；不切换 SDD，不派发代码 implementer／task reviewer／fixer。
- 前端视觉：继承已确认原型及 VS-001，不要求 Figma；真实视觉与 E2E 门禁仍保留。
- Task-owner checkbox 是唯一完成权威；此文件只记录恢复和验证证据，不把计划检查算成软件实现。

## Pre-flight Plan Review

- Canonical 表示、manifest 顺序、唯一任务 owner、64 个未完成任务和 27 条跨端依赖已核对；不存在 small/split 双形式、历史设计入口、重复 checkbox 或依赖环。
- 已确认的提案、两端设计、Global Constraints、接口账本和任务验证边界作为实现依据；每项执行前再读取其唯一 owner 中的完整任务。
- 初始 Git 分支为 `main`；只有既存 `docs/`、`fp-docs/` 未跟踪内容，无生产后端或前端工程。不覆盖或提交无关调研资料。
- 测试 seams 已由用户确认的各任务 Interfaces／Contract checks 指定；执行时逐行为 RED → GREEN，不先批量写完测试或实现。
- Bundled runtime：Python 3.12.14、Node v24.21.0、pnpm 11.28.5。前端命令使用 bundled Node 与 pnpm 脚本，PATH 仅在当前子进程绑定，不改变全局配置。
- 启动时 `.codegraph/` 不存在，CodeGraph 为 N/A；不隐式初始化或查询代码图。
- 用户后续批准先在 Windows 开发可移植后端能力；目标 Linux 运行、容器及源站验收仍未具备。Windows 单测不等价于 Linux 专属行为、正式 HTTPS 或真实来源验证。
- 云主机、HTTPS 域名、私密凭据、来源许可、实际源图和维护演练仍是后续任务的真实前提；尚无视觉／E2E 阶段或正式交付通过记录。

## Completed

- `backend-032`（owner：[55-schedule-backup-tasks.md](<../tasks/backend/55-schedule-backup-tasks.md>)）：commit `84b1dd984c9af81808e50bc30611e0da7c5a0a0f..09e57a204bef92b829e4e7838d55c0888399ff0b`。RED：restore_backup缺失；GREEN：Windows venv backup9/9，全后端213/213；compileall/pip check/staged diff检查通过。确认文本必须精确，API lifespan/worker持application lease，恢复需非阻塞独占lease并再取SQLite EXCLUSIVE；坏文件/运行中拒绝。覆盖前在线一致性保存独立pre-restore，备份/staged七表+alembic+integrity校验后清理sidecar并原子替换，重开验证标题/收藏/任务；README记录Compose停写、损失窗口、迁移、重启检查和pre-restore回滚。Windows真实锁/文件往返已测，Linux flock/卷恢复仍backend-038/043门禁；inline自审clean，提交六文件，未push。

- `backend-031`（owner：[55-schedule-backup-tasks.md](<../tasks/backend/55-schedule-backup-tasks.md>)）：commit `ab7eb585599e7ba0080ae2fcb74624c66011c874..84b1dd984c9af81808e50bc30611e0da7c5a0a0f`。RED：backup模块缺失；首轮Windows失败暴露sqlite3连接context不自动close导致临时文件锁，改为closing后通过。GREEN：Windows venv backup/schedule14/14，全后端209/209；compileall/pip check/staged diff检查通过。使用SQLite backup API，源/快照integrity_check、七业务表及alembic版本验证后chmod+原子replace，再轮换最近七份；上海日期/同日幂等。磁盘/未迁移/缺库失败保留旧份并安全记录，下个空闲tick重试，网络任务优先不并行备份。inline自审clean，同机备份不冒充灾备，提交四文件，未push。

- `backend-030`（owner：[55-schedule-backup-tasks.md](<../tasks/backend/55-schedule-backup-tasks.md>)）：commit `df4e1232945634e2190c0e7abc28903736ce89ff..ab7eb585599e7ba0080ae2fcb74624c66011c874`。RED：首次独立进程测试未进入暂停点；改用真实`subprocess`而非stdin/spawn后通过。GREEN：Windows venv recovery/jobs/schedule17/17，全后端204/204；compileall/pip check/staged diff检查通过。子进程认领并将第二入口running短提交，进入无DB事务的合成网络等待；父进程真实API继续读取第一入口已提交标题/收藏，terminate后重开结算，仅unfinished进入catchup。`job_interrupted`只在提交成功后带job_id记录；注入commit/disk错误无事件且running回滚。stdout/stderr不含内容哨兵。此为本地合成元信息和Windows进程证据，不是Linux/真实来源验收；inline自审clean，提交两文件，未push。

- `backend-029`（owner：[55-schedule-backup-tasks.md](<../tasks/backend/55-schedule-backup-tasks.md>)）：commit `897e753dff4a81d0ae02a40a3f9f5efbacf3d5f5..df4e1232945634e2190c0e7abc28903736ce89ff`。RED：catchup_due缺失；GREEN：Windows venv schedule+worker14/14，全后端202/202；compileall/pip check/staged diff检查通过。北京时间07:30后，当天无schedule全选eligible；有结果只补非succeeded与当前eligible交集；成功日程不补、禁用剔除、无候选不耗次数、活动手动终态后再补。catchup持久行实现重复重启一次上限，双连接并发仅一条，不追昨日。tick固定schedule后catchup。inline自审clean，真实重启/时间证据仍backend-042，提交两文件，未push。

- `backend-028`（owner：[55-schedule-backup-tasks.md](<../tasks/backend/55-schedule-backup-tasks.md>)）：commit `4d04df71e7070e8a82def8abf98b6c6ca4e2d9ed..897e753dff4a81d0ae02a40a3f9f5efbacf3d5f5`。RED：schedule模块缺失；GREEN：Windows venv schedule+worker9/9，全后端197/197；compileall/pip check/staged diff检查通过。按Asia/Shanghai仅07:30分钟窗口、当日本地date创建schedule；前后不回放，活动手动任务优先，schedule/catchup任一同日记录阻止重复；双连接并发只一条。worker先处理pending再空闲tick。Windows缺IANA数据时仅开发回退固定UTC+8，Linux仍ZoneInfo；真实07:30归backend-042。inline自审clean，提交三文件，未push。

- `backend-027`（owner：[50-job-tasks.md](<../tasks/backend/50-job-tasks.md>)）：commit `e41addd480d80bfc46dcc87d9fe8521f9f87fa7f..4d04df71e7070e8a82def8abf98b6c6ca4e2d9ed`。RED：settle_interrupted缺失；GREEN：Windows venv worker5/5，全后端193/193；compileall/pip check/staged diff检查通过。worker锁→application lease后启动即结算旧running，job置interrupted/finished；只把pending/running结果中断，原succeeded/failed计数和错误不变，阅读条目/收藏保留；正常pending不取消，活动唯一索引释放后可新建。幂等重跑验证通过；Linux真实重启仍归backend-042。inline自审clean，提交两文件，未push。

- `backend-026`（owner：[50-job-tasks.md](<../tasks/backend/50-job-tasks.md>)）：commit `d146651d7c9a239b703e548edc548449d6f89c06..e41addd480d80bfc46dcc87d9fe8521f9f87fa7f`。RED：worker模块缺失；GREEN：Windows venv worker+ingest24/24，全后端192/192；compileall/pip check/staged diff检查通过。UPDATE…RETURNING双连接仅一次claim并立即提交；每入口running短提交后释放事务再fetch，成功条目/last_success/EntryResult同事务，失败另短事务写安全错误，最终succeeded/partial/failed正确，零条为成功。Windows标准库真实文件锁拒绝第二实例，网络阶段另一Session可提交。生产代码分支仍使用`fcntl.flock`共享/独占语义，但当前未在Linux运行；必须在backend-038镜像和backend-042真实进程演练重跑，否则发布阻塞。inline自审clean，提交四文件，未push。

- `backend-025`（owner：[50-job-tasks.md](<../tasks/backend/50-job-tasks.md>)）：commit `9cbd43303b86241d6ce151e3c762767bfc674bd7..d146651d7c9a239b703e548edc548449d6f89c06`。RED：任务API路由404；GREEN：Windows venv jobs API/service9/9，全后端188/188；compileall/pip check/staged diff检查通过。current固定路由优先且无记录null；创建/重试新任务202、活动复用200；详情按EntryResult聚合计数并返回来源身份。GET会话保护、POST会话+Origin+CSRF、非法trigger/额外字段400、缺任务404均验证。API只读写SQLite不fetch；inline自审clean，提交四文件，未push。

- `backend-024`（owner：[50-job-tasks.md](<../tasks/backend/50-job-tasks.md>)）：commit `cd01d11dc581005f9e50a44c5a0a5ebab39de3c8..9cbd43303b86241d6ce151e3c762767bfc674bd7`。RED：retry_job缺失；GREEN：Windows venv jobs6/6，全后端185/185；compileall/pip check/staged diff检查通过。不存在优先404，已有活动直接复用；否则仅原failed/interrupted与当前eligible交集创建retry，成功/pending/running及后来禁用入口排除，无候选409。原任务状态/计数保持不变且不访问网络；inline自审clean，提交两文件，未push。

- `backend-023`（owner：[50-job-tasks.md](<../tasks/backend/50-job-tasks.md>)）：commit `e066be69eae760655b615ee32248d134da06d198..cd01d11dc581005f9e50a44c5a0a5ebab39de3c8`。RED：jobs模块缺失；GREEN：Windows venv jobs4/4，全后端183/183；compileall/pip check/staged diff检查通过。刷新只创建数据库Job+每合格入口唯一EntryResult；独立Session并发最终同一ID且一新一复用，pending/running优先，终态后可新建；无enabled入口409。外键失败回滚无半任务，同日日程终态由日期唯一约束复用。未调用来源网络；inline自审clean，提交两文件，未push。

- `backend-022`（owner：[45-ingestion-tasks.md](<../tasks/backend/45-ingestion-tasks.md>)）：commit `8cf007498f0d23ba789693ff983c18b5a3ebc619..e066be69eae760655b615ee32248d134da06d198`。RED：ingest_entry/safe_error缺失；GREEN：Windows venv ingest/parser/upsert45/45，全后端179/179；compileall/pip check/staged diff检查通过。每次复核eligible后仅一次SafeClient fetch，媒体类型匹配固定RSS/list分支，加载本地规则分类，图片再次许可过滤，按链接幂等写；条目、last_success和可选EntryResult计数同事务提交。合法零条成功，禁用入口/脏Session在fetch前失败；过大/畸形/中途第二条失败/错误result_id全回滚且safe_error不回显哨兵。未持SQLite写锁等待网络。inline自审clean，提交三文件，未push。

- `backend-021`（owner：[45-ingestion-tasks.md](<../tasks/backend/45-ingestion-tasks.md>)）：commit `38e181213f3d1dbc107273130c0df79de4526f34..8cf007498f0d23ba789693ff983c18b5a3ebc619`。RED：ingest图片边界缺失；GREEN：Windows venv ingest11/11，全后端170/170；compileall/pip check/staged diff检查通过。图片许可false一律无图；true仍只保留精确IDNA白名单的HTTPS443无凭据域名，拒绝data/file/http、后缀伪装、控制字符、超长和任何IP字面量。署名独立限500且无效只置NULL。测试patch网络调用证明函数不下载/探测；inline自审clean，无代理/缓存/图片表，提交两文件，未push。

- `backend-020`（owner：[45-ingestion-tasks.md](<../tasks/backend/45-ingestion-tasks.md>)）：commit `8147db773bc590ce0e89746bf3b88b2bd402b600..38e181213f3d1dbc107273130c0df79de4526f34`。RED：ListSelection/parse_list缺失；GREEN：Windows venv parsers11/11，全后端159/159；compileall/pip check/staged diff检查通过。仅唯一核验container内固定item/title/link/date/section/image/credit选择器；script/style/noscript/template删除，不解释body，不请求详情。未核验/非法CSS/容器错结构/无明确empty标记均ParseError；缺字段、危险href逐条跳过，相对链接按固定入口URL解析。inline自审clean，配置仍无虚构站点CSS，提交两文件，未push。

- `backend-019`（owner：[45-ingestion-tasks.md](<../tasks/backend/45-ingestion-tasks.md>)）：commit `69f7938c191c6fafac51dc2e7a5c4ab0b825209a..8147db773bc590ce0e89746bf3b88b2bd402b600`。RED：parsers模块缺失；GREEN：Windows venv RSS/RDF7/7，全后端155/155；compileall/pip check/staged diff检查通过。只提取直接title/link/pubDate/DC date/category和明确media thumbnail/image enclosure/credit；description/content/summary哨兵不进入对象/repr。DTD/实体/畸形/未知结构抛ParseError，合法空channel零条，危险URL和缺字段逐条计数，日期无效保留标题并置NULL。inline自审clean，无正文日志/详情请求，提交两文件，未push。

- `backend-018`（owner：[40-source-security-tasks.md](<../tasks/backend/40-source-security-tasks.md>)）：commit `a8a0768b1271bbe159ff421872e53e86a75353ca..69f7938c191c6fafac51dc2e7a5c4ab0b825209a`。RED：SafeClient/FetchError/Limits缺失；GREEN：Windows venv safe_http40/40，全后端148/148；compileall/pip check/staged diff检查通过。生产拨号socket只连Target.ip，TLS SNI/证书及Host仍用原域名；最多3跳/4请求且每跳重新解析验证，无自动重试。连接5s/读取10s/总30s、2MiB双重长度限制，拒绝压缩、未知媒体、非200、截断、循环/私网跳转；所有连接finally关闭。内存http_lab验证第二次DNS变化、chunk超限与总预算，不真实联网。inline自审clean，提交三文件，未push。

- `backend-017`（owner：[40-source-security-tasks.md](<../tasks/backend/40-source-security-tasks.md>)）：commit `832e25d73ee502d01f116e16ae2af3762a015a9d..a8a0768b1271bbe159ff421872e53e86a75353ca`。RED：safe_http缺失；GREEN：Windows venv安全目标24/24，全后端132/132；compileall/pip check/staged diff检查通过。严格HTTPS443、无凭据/IP字面/后缀伪装/控制字符；IDNA精确主机；每次解析全部地址均须公网，混合DNS、私网/loopback/link-local/shared/reserved/multicast/IPv4映射IPv6均拒绝，Target只携已验证固定IP。生产getaddrinfo在spawn子进程内最多5秒，超时terminate/join回收；测试验证清理。未真实联网；inline自审clean，提交两文件，未push。

- `backend-016`（owner：[40-source-security-tasks.md](<../tasks/backend/40-source-security-tasks.md>)）：commit `41509ce9dbf2042b6eeaa676e983cb4863d4e808..832e25d73ee502d01f116e16ae2af3762a015a9d`。RED：逐入口许可/来源API函数缺失，随后GET路由404；GREEN：Windows venv sources13/13，全后端108/108；compileall/pip check/staged diff检查通过。allowed需原因/依据及自动读取+标题保存明确许可，enabled再需probe成功且最终主机在固定范围；pending/restricted不探测，运行失败保留许可与last_success并单独记录last_error。网站partial只汇总，不放行其它入口；来源API登录只读、五站六入口字段精确。安全JSON原子证据拒绝密码/Cookie/CSRF/token/raw body/html。inline自审clean，未联网或生成正式许可，提交四文件，未push。

- `backend-015`（owner：[40-source-security-tasks.md](<../tasks/backend/40-source-security-tasks.md>)）：commit `0751b895232669e8882b9daff850b8264e707ce8..41509ce9dbf2042b6eeaa676e983cb4863d4e808`。RED：app.sources 缺失；GREEN：Windows venv sources5/5，全后端100/100；compileall/pip check/staged diff检查通过。配置严格固定五站六入口，PR TIMES 两入口共享站点；全部pending/disabled，二次seed不覆盖许可或last_success，配置内预授权/动态provider/第七入口/站点元数据冲突被拒绝，运行绑定只接受固定身份。未联网、未认定许可或结构可用，图片默认禁用；inline自审clean，提交三文件，未push。

- `backend-014`（owner：[30-reading-tasks.md](<../tasks/backend/30-reading-tasks.md>)）：commit `1dd4be66c3bd661e231fa21c165ecdd53419b6f5..0751b895232669e8882b9daff850b8264e707ce8`。RED：收藏路由404；GREEN：Windows venv bookmark API/service6/6，全后端95/95；compileall/pip check/staged diff检查通过。匿名401、缺CSRF/错误Origin403、非法筛选/额外字段400、缺条目404、存储异常安全503及失败后原状态保持均经真实TestClient与SQLite验证。列表/详情/收藏/写响应的bookmarked同义，PUT/DELETE幂等且取消不删资讯。inline自审clean，无快照或乐观假成功，提交三文件，未push。

- `backend-013`（owner：[30-reading-tasks.md](<../tasks/backend/30-reading-tasks.md>)）：commit `9ac03722bf6202767f5729373d5a6697c3fe5ff2..1dd4be66c3bd661e231fa21c165ecdd53419b6f5`。RED：收藏 service 缺失；GREEN：Windows venv bookmark/upsert17/17，全后端92/92；compileall/pip check/staged diff检查通过。重复收藏不重置时间、同时间按article_id倒序、重连持久、同链接标题更新跟随、取消不删Article和404不存在均验证；提交异常真实rollback并不返回成功DTO。inline自审clean，无标题快照/客户端排序，提交两文件，未push。

- `backend-012`（owner：[30-reading-tasks.md](<../tasks/backend/30-reading-tasks.md>)）：commit `b85f634ec54558e7d3b265ac69de7adf542d5fa3..9ac03722bf6202767f5729373d5a6697c3fe5ff2`。RED：读取路由404；GREEN：Windows venv articles API + query 17/17，全后端89/89；compileall/pip check/staged diff检查通过。列表/详情/filters均需真实服务器会话，响应模型只含白名单标题元信息和bookmarked；NULL、七类、请求ID、400非法/重复筛选、404缺条目语义均经TestClient验证。request依赖使用独立Session，避免跨线程复用测试Session。inline自审clean，无正文/摘要/事件字段、无匿名差异泄漏；提交四文件，未push。

- `backend-011`（owner：[30-reading-tasks.md](<../tasks/backend/30-reading-tasks.md>)）：commit `a924c6ef37590f8d276eb4d1d088321a51f5af11..b85f634ec54558e7d3b265ac69de7adf542d5fa3`。RED：ArticleQuery 等查询契约缺失；后续 bookmarked-only join 暴露 EXISTS 自动关联错误、超大页码未拒绝，均先由测试失败再修复。GREEN：Windows venv queries14/14，全后端86/86；compileall/pip check/staged diff检查通过。组合条件交集、JSON多分类、NULL未知、日期含界、%/_字面搜索、服务端bookmarked、首页日期/ID与收藏时间/ID排序、动态选项、总数/页码及已确认跨更新位移均验证。inline自审clean，无全文索引/快照/客户端排序；提交两文件，未push。

- `backend-010`（owner：[30-reading-tasks.md](<../tasks/backend/30-reading-tasks.md>)）：commit `5410cd09005485fec5e704eb5d2d9281b34b20ba..a924c6ef37590f8d276eb4d1d088321a51f5af11`。RED：classification 模块缺失；GREEN：多语分类4/4，全后端72/72；compileall/pip check/staged diff检查通过。固定七类按产品顺序去重，规则逐条含evidence并只消费标题/栏目；未知保留空，媒体国别不推断市场，多地区/多品类冲突返回NULL，非法字段/分类/正则拒绝。inline自审clean，不引入模型或正文，不承诺完整覆盖；提交三文件，未push。

- `backend-009`（owner：[30-reading-tasks.md](<../tasks/backend/30-reading-tasks.md>)）：commit `0cf5fc6b5ee715235db4f3efe72bd120433649c8..5410cd09005485fec5e704eb5d2d9281b34b20ba`。RED：app.articles 缺失；后新增超长片段/控制字符URL和来源入口不匹配的负向测试先失败再修复。GREEN：Windows venv upsert 14/14，全后端68/68；compileall/pip check/staged diff检查通过。链接身份只移除空格和#，参数顺序/大小写/媒体保持独立；同链接可靠字段更新、缺值不擦除旧日期/分类/图片、首次来源和收藏关系不变；两独立SQLite会话并发写最终单一ID。输入安全边界不发网络，拒绝凭据URL/非HTTPS图和超界字段。inline自审clean，仅提交两文件，未push。

- `backend-008`（owner：[20-auth-tasks.md](<../tasks/backend/20-auth-tasks.md>)）：commit `42179f683b8762cc7a94e8dba773a950edf1d28f..0cf5fc6b5ee715235db4f3efe72bd120433649c8`。RED：首登路由404；GREEN：Windows venv 认证接口 8 项，password/session 组合16项，全后端54/54；compileall、pip check、staged diff 检查通过。首次登录无旧CSRF但在请求体解析前检查精确Origin/JSON/16KiB；Pydantic限制密码与额外字段；Cookie Secure/HttpOnly/SameSite=Strict/Path=/；已登录写请求依次验证会话、Origin、constant-time CSRF，退出撤销摘要。错误登录/限流/过期/退出失败语义均经真实TestClient和临时SQLite验证。inline 自审 clean，未输出密码/Cookie或打开文档端点；线上网关和真实HTTPS尚待Linux任务，提交四文件，未push。

- `backend-007`（owner：[20-auth-tasks.md](<../tasks/backend/20-auth-tasks.md>)）：commit `6e487dfe0ddbb43908dee7c7c84f2ca674c37067..42179f683b8762cc7a94e8dba773a950edf1d28f`。RED：issue_session 等函数缺失；GREEN：Windows venv `pytest -q` 全后端 47/47（会话 6 项），compileall/pip check/staged diff 检查通过。真实临时 SQLite 验证随机令牌只存摘要、稳定 HMAC 标记、24h 到期边界、重复撤销及新连接立即观察撤销；无效令牌统一401。inline 自审 clean，AuthOut repr 隐藏 CSRF、密钥不入库；此任务没有 HTTP 登录路由或线上验收通过事实，提交两文件，未 push。

- `backend-006`（owner：[20-auth-tasks.md](<../tasks/backend/20-auth-tasks.md>)）：commit `9eb2da70af224e5e3810115eb48cd38bc1773d73..6e487dfe0ddbb43908dee7c7c84f2ca674c37067`。RED：app.auth 缺失；GREEN：Windows venv 密码/两级窗口/并发配额/可信网关测试 3/3，连同模型和启动测试共 41/41；staged diff 检查通过。Argon2id 验证不记录密码，错误摘要拒绝；原子一分钟 30 次全局配额、每地址 15 分钟五次失败、窗口恢复、伪造转发头防护均在单元边界验证。inline 自审 clean，限流为单实例内存状态、重启重置，未宣称生产防爆破验收；仅提交两文件，未 push。

- `backend-005`（owner：[10-foundation-tasks.md](<../tasks/backend/10-foundation-tasks.md>)）：commit `93d44f3e3a624430b9c332747b4dcc43a2703667..9eb2da70af224e5e3810115eb48cd38bc1773d73`。RED：完整迁移结果缺 sessions；其后时区往返测试证实 SQLite 原始 DateTime 丢失时区，修复为显式 UTC 类型后通过。GREEN：Windows venv `pytest tests/test_schema.py tests/test_bootstrap.py -q` 38/38，compileall、pip check、staged diff 检查通过。实际 head→base→head 恰七业务表，摘要唯一/过期索引，所有事件时间读写 UTC，不创建正文/图片字节/明文凭据列。inline 自审 clean，迁移只针对新空测试库，真实线上回滚依然要求独立授权和备份；提交本任务三文件，未 push。

- `backend-004`（owner：[10-foundation-tasks.md](<../tasks/backend/10-foundation-tasks.md>)）：commit `9eb04e804588f791dce9ffd498bee7104aedcdfa..93d44f3e3a624430b9c332747b4dcc43a2703667`。RED：任务模型/结果缺失导致新约束测试失败；GREEN：Windows venv `pytest tests/test_schema.py tests/test_bootstrap.py -q` 36/36，compileall 与 staged diff 检查通过。0003 迁移真实验证活动任务部分唯一索引、日程/补跑每日唯一、日期不可空、终态结束时间、入口结果组合唯一/非负计数；两个独立 Session 竞争只能一个提交。这里证明数据库并发约束，尚未实现 worker 或 Linux flock；inline 自审 clean，仅提交四任务文件，未 push。

- `backend-003`（owner：[10-foundation-tasks.md](<../tasks/backend/10-foundation-tasks.md>)）：commit `72d57f5ea9769dcbd55ac5414c7ea52829a71c06..9eb04e804588f791dce9ffd498bee7104aedcdfa`。RED：新增真实数据库测试因 Article 尚不存在失败；GREEN：Windows venv `cd backend && python -m pytest tests/test_schema.py tests/test_bootstrap.py -q` 25/25；compileall 与 staged diff 检查通过。新增 0002 资讯／收藏表，BINARY 链接唯一性、查询参数差异、日期可空、分类 JSON 数组、收藏外键和主键、两类排序索引均由临时数据库验证。无正文／事件／图片字节表，没有真实来源数据；inline 自审 clean，提交本任务四文件，未 push。

- `backend-002`（owner：[10-foundation-tasks.md](<../tasks/backend/10-foundation-tasks.md>)）：commit `91ac038521243dafab6f1bb9edc8140f06c45159..72d57f5ea9769dcbd55ac5414c7ea52829a71c06`。RED：真实 SQLite 迁移测试因缺少 app.database 失败；GREEN：Windows 仓库 venv 的 `cd backend && python -m pytest tests/test_schema.py tests/test_bootstrap.py -q` 19/19 通过；`python -m compileall -q app tests alembic`、`pip check`、`git diff --cached --check` 通过。实际运行 0001 来源／入口迁移、downgrade/base/re-upgrade；每新连接 FK 开启、busy_timeout 5000；同站 URL 唯一、孤儿外键、无许可依据启用、受限启用与非法类型均被真实数据库拒绝。入口许可独立，未读取外站、未创建生产库或记录真实授权。inline 自审 clean，迁移代码不导入当前模型构造表，来源许可与访问错误分离；仅提交任务七文件，未 push。

- `backend-001`（owner：[10-foundation-tasks.md](<../tasks/backend/10-foundation-tasks.md>)）：commit `900d577f9221725c25005f263339ccd59c0b4cea..91ac038521243dafab6f1bb9edc8140f06c45159`。用户明确批准 Windows 本地开发，使用 `backend/.venv/Scripts/python.exe`（Python 3.12.14）。RED：依赖安装完成后缺少 `app.errors`，随后分别通过失败测试发现未知异常未记录关联日志、配置 repr 泄露测试凭据、无效 Argon2id 摘要未拒绝。GREEN：`cd backend && python -m pytest tests/test_bootstrap.py -q` 8/8；`python -m compileall -q app tests`、`python -m pip check`、`git diff --cached --check` 通过。inline 自审：导入不联网／建库，配置无默认密码，固定 JSON 错误不回显请求或异常正文，日志只记 request_id/异常类型，测试专用口令不用于生产。仅提交任务九文件，无 venv/缓存/真实配置、未 push。保留 Starlette TestClient 使用 httpx 的弃用警告，未擅自增加 httpx2；此结果仅为 Windows 可移植测试，不是 Linux／HTTPS／真实来源验收。

- `frontend-001`（owner：[10-foundation-tasks.md](<../tasks/frontend/10-foundation-tasks.md#L5-L59>)）：commit `27c016f62984c3e1e9732f08201b92f24d4da9ca..19dbb275eabb67eff3378cb9cb09443aa3b7c893`。实际 RED 先为缺少 `src/main.ts`；随后分别验证缺少静态检查工具、漏拦旧演示入口、漏拦服务端凭据标记，均在最小实现前失败。GREEN：bundled Node/pnpm 下 `--dir frontend run test:unit -- tests/unit/bootstrap.spec.ts`，4/4 通过；`run typecheck`、`run build`、`run check:artifact` 均退出 0；`git diff --cached --check` 通过，inline 自审 clean。实际 build identity：`d96594b5b586fae7127c15174648cd7f5bed87ebd1255b79003382bb5ce00ea2`。纯工程任务，无产品 UI case，不声称视觉或真实 E2E 通过；Git 只提交本任务 16 个前端文件，生成物忽略，未 push。
- `frontend-002`（owner：[10-foundation-tasks.md](<../tasks/frontend/10-foundation-tasks.md#L62-L116>)）：commit `19dbb275eabb67eff3378cb9cb09443aa3b7c893..c85466526d8bdc38f3be8aa110d70ac6b4bb8936`。RED：来源映射不存在；之后变更来源 hash／换成运行截图／路径失真等单元反例，检查工具尚不存在而失败。GREEN：bundled Node/pnpm `--dir frontend run test:unit tests/unit/visual-source.spec.ts` 4/4 通过；`--dir frontend run source-check` 对原型、桌面／平板／手机静态图、确认前端设计、本地字体和 OFL 许可逐项核对真实 SHA-256，结果 `runtimeVisualReviewed:false`；`run typecheck`、`run build`、`run check:artifact` 均退出 0；完整 frontend unit 8/8 通过，`git diff --cached --check` 通过，inline 自审 clean。JPEG SOF 高宽字段第一次读反导致 source-check 非零，已与只读 Pillow 尺寸核对并修正后重跑通过。纯来源冻结任务，无产品 UI case，不声称新页面视觉 PASS 或真实 E2E 通过；仅提交本任务四个前端文件，未 push。
- `frontend-003`（owner：[10-foundation-tasks.md](<../tasks/frontend/10-foundation-tasks.md#L118-L174>)）：commit `c85466526d8bdc38f3be8aa110d70ac6b4bb8936..bead53d9dde1f1496a161cac73696b4e8f024073`。RED：首先导入 `src/api/client.ts` 不存在；后逐条验证响应读取时的 AbortError 不得吞掉、未确认会话不得视作登录、列表缺 `bookmarked` 不得猜测、来源入口状态不能用网站级 `partial`、更新结果复用标记不能是字符串、缺值筛选哨兵必须与后端一致。GREEN：bundled Node/pnpm `--dir frontend run test:unit tests/unit/api-client.spec.ts`，9/9 通过；`run typecheck`、`run build`、`run check:artifact`、`run source-check` 全部退出 0；完整 frontend unit 17/17 通过；`git diff --cached --check` 通过，inline 自审 clean。只构建固定同源 `/api/` 方法，不写 Cookie/Origin、不自动重试写、不假称 unit-only 夹具是 E2E；产物仍是先前空路由 shell，非真实 UI case。只提交本任务四个文件，未 push。
- `frontend-004`（owner：[10-foundation-tasks.md](<../tasks/frontend/10-foundation-tasks.md#L176-L234>)）：commit `bead53d9dde1f1496a161cac73696b4e8f024073..0a0a0f81939b2b9cbc184dfe6b264536bf6cabe7`。RED：最先因 `src/state/session.ts` 缺失；又分别验证旧会话 GET、注销回复和受保护写入的迟到 401 不能清除新登录（这三轮先失败后修复）。GREEN：bundled Node/pnpm `--dir frontend run test:unit tests/unit/session.spec.ts` 7/7 通过，完整单元 24/24；`run typecheck`、`run build`、`run check:artifact` 和 `run source-check` 均退出 0，`git diff --cached --check` 通过，inline 自审 clean。内存保管服务端会话与 CSRF，ensure 并发共用 GET，401 清理并阻止写入自动重放，403 注销失败不假报成功，凭据不落 Storage；模块导入不发请求。无产品 UI case，不声称真实会话或浏览器 E2E 通过；只提交本任务三文件，未 push。
- `frontend-005`（owner：[10-foundation-tasks.md](<../tasks/frontend/10-foundation-tasks.md#L236-L290>)）：commit `0a0a0f81939b2b9cbc184dfe6b264536bf6cabe7..ab1a6cb8e145722d2353a4f6cd356a302ecac794`。RED：先因 `src/state/query.ts` 缺失失败；GREEN：bundled Node/pnpm `--dir frontend run test:unit tests/unit/query.spec.ts` 4/4 通过，完整前端 unit 28/28；`run typecheck`、`run build`、`run check:artifact`、`run source-check` 均退出 0；`git diff --cached --check` 通过，inline 自审 clean。固定七类和缺值哨兵，重复／未知 key、非法闰日与日期倒置、q 与页码边界均有行为测试；safeReturn 只接受已知站内路径和合法阅读条件，拒绝站外回跳及无关敏感参数。未持久化密码、CSRF 或客户端资讯缓存，没有 API 或浏览器 E2E 通过事实。仅提交本任务两个文件，未 push。
- `frontend-008`（owner：[30-reading-tasks.md](<../tasks/frontend/30-reading-tasks.md#L3-L70>)）：commit `ab1a6cb8e145722d2353a4f6cd356a302ecac794..900d577f9221725c25005f263339ccd59c0b4cea`。RED：首先因 `src/state/headlines.ts` 缺失；随后增加服务器撤销会话时不得继续显示旧个人页的失败测试，再修复。GREEN：bundled Node/pnpm `--dir frontend run test:unit tests/unit/headlines.spec.ts` 8/8 通过，完整单元 36/36；`run typecheck`、`run build`、`run check:artifact`、`run source-check` 均退出 0；`git diff --cached --check` 通过，inline 自审 clean。显式 load、不在导入时请求；新条件清旧列表，同条件重读失败保留已确认页，来源过滤失败不伪造空选项；旧请求、卸载请求按序号和 AbortSignal 忽略；服务端收藏列表不作客户端整库筛选。仅 unit-only 边界夹具，无真实 API 或浏览器 E2E；只提交本任务两文件，未 push。

## Blocked

- `backend-033`：当前唯一依赖就绪任务。用户说明目标为既有腾讯云服务器；具体 SSH 地址、账号和主机指纹属于本地基础设施信息，不进入 Git。已读取 PR TIMES 当前官方使用条款与 robots：一般规约第3条允许一般用户/访客为信息阅览/取得、私用复制或引用使用企业内容，第6条禁止超范围和有偿使用；robots总体Allow `/`。这支持继续核验本单人非商业标题/链接用途，但RSS与Beauty仍须分别probe且不得扩展正文。目标连接首次只读检查因 `REMOTE HOST IDENTIFICATION HAS CHANGED` 失败；未关闭StrictHostKeyChecking、未改known_hosts、未执行远端命令。需用户通过腾讯云控制台带外核对服务器主机指纹后才可继续。用户随后直接指示“先不要连接服务器”；执行已停止任何远端尝试。当前未访问采集入口、未生成 `backend/verification/prtimes.json`、未probe或启用来源，owner checkbox保持未勾选。
- Linux 独有的 `fcntl`／flock、Docker Compose、正式 HTTPS、许可来源与真实 E2E 仍待目标 Linux 环境；backend-026/032 checkbox代表代码与Windows可移植语义完成，不代表这些发布门禁通过。
- 执行环境变更证据：用户在 `fp-execute-linux-environment-gate` 的直接答复为“先在当前win环境完成开发，线上linux环境通过dockers compose部署”。已确认的最终架构、64 个 task ID、唯一 owner、依赖和 UI/E2E 门禁不变。仅定点修改 [后端约束](<../tasks/backend/01-context.md>)与 [backend-001](<../tasks/backend/10-foundation-tasks.md#L3-L60>) 的开发机命令和 venv 忽略文件；后续 Linux 专属行为仍必须在目标环境验证。此前 Docker／Podman 不在 PATH、WSL 未安装的记录是旧阻塞的事实，不是现在 Windows 本地开发阻塞。

## Notes

- 后端安装 job `win-bash-f7b055231d6a4f1e` 已结束并收取，退出 0。仓库 venv 内实际版本：FastAPI 0.162.0、Pydantic 2.14.1、uvicorn 0.54.0、SQLAlchemy 2.1.6、Alembic 1.20.1、argon2-cffi 25.1.0、defusedxml 0.7.1、BeautifulSoup 4.15.0、pytest 9.2.0、httpx 0.28.1、Starlette 1.10.0；均在已列主版本范围内，未修改全局 Python 或升级 pip。

- 已完成 backend-001～032 与 frontend-001～005/008；当前由 owner checkbox 派生38/64。依赖图唯一就绪项为真实许可任务 backend-033；不跳过它实施依赖的发布或UI-bearing任务。
- 单元夹具不能作为真实前端 E2E；所有 UI case 的执行证据尚未创建，未签发任何 `VISUAL_REVIEW_PASS` 或 `FRONTEND_E2E_PASS`。
- 每个任务只在验证、inline 自审和对应提交步骤满足后更新其唯一 checkbox，并从 checkbox 重算 overview。

## Task notes — frontend-001

- 依赖安装 job：`win-bash-e1430f098f5a4141`，已收取结果；初次退出 1 为 pnpm 的 `ERR_PNPM_IGNORED_BUILDS`，不是业务 RED。`pnpm why esbuild` 确认唯一版本 0.28.2，为 Vite 7.3.7 所需；只运行本项目 `approve-builds esbuild`，生成 `frontend/pnpm-workspace.yaml` 的 `allowBuilds.esbuild: true`，未放行全部脚本或升级全局工具。已先把必要新配置加入该任务 Files／文件结构。
- 实际依赖：Vue 3.5.44、Vue Router 4.6.4、Vite 7.3.7、TypeScript 5.9.3、Vitest 4.1.12、vue-tsc 3.3.13、Vue Test Utils 2.5.1、jsdom 27.4.0、plugin-vue 6.0.10、Node types 24.19.2；锁定文件已随代码提交。
- inline 自审：最小 App 仅路由出口，没有业务演示数据或接口代理；静态检查工具只读本地构建、校验引用并输出摘要，不执行 JavaScript。旧演示路径与明确凭据标记均有先 RED 后 GREEN 的拒绝测试，普通 Object.prototype 不误报；工具不宣称能证明全部秘密、业务或视觉正确。临时文件只在各测试自建目录内清理。
- Git 未包含无关 `docs/` 或旧原型，未提交 node_modules／dist，未 push。启动时无 CodeGraph，本任务不运行 init/sync。下一项为 `frontend-002`。

## Commit review repairs — 2026-10-28

- P003/F03 自审发现 `frontend/src/api/client.ts` 的 `logout()` 曾接受任意 HTTP 200 JSON，可能在服务器未确认撤销时清除本地会话。新增 `api-client.spec.ts` 负向用例先以“promise resolved `{authenticated:true}`”失败，再要求精确 `{authenticated:false}` 后通过；目标测试 10/10、typecheck 通过。
- P003/F03 独立审查发现较早 `login()` 回复可覆盖后来登录或 `clear()`。新增两条 `session.spec.ts` 竞态用例，先分别以旧 CSRF 覆盖和旧登录复活失败；登录代次防护实现后目标测试 9/9、typecheck 通过。上述修复不改变任务完成数或真实 E2E 状态。
- 工程质量审查补齐公开任务/文章 DTO、迁移 URL helper 与 `changeFilters` 的职责说明；在 `worker.py` 记录单机 SQLite＋串行 worker 的 `fp-debt` 理由、单机上限、实测触发条件和 PostgreSQL/队列升级方向。
- 提交前移除执行 ledger 中的具体腾讯云 SSH 地址、账号和主机指纹；只保留带外核验阻塞事实。将 task context 的本机插件绝对路径改为 workspace-contract 可解析的插件相对路径，并把“任务均未执行／工程不存在”等规划时陈述标明为历史生成事实，避免与 owner checkbox 和当前源码冲突。三份 `docs/` 经用户本轮明确选择纳入，但均标为历史调研/非 canonical，普通计划的分类编码同步到当前接口账本。
- 更正上述登录竞态实现说明：revision 只能保护内存，不能阻止浏览器按响应顺序处理 Cookie。最终实现用同一认证 mutation 队列串行 login/logout，测试确认第二个登录及新登录会等待前一个认证写完成；`api-client.spec.ts` 12/12、`session.spec.ts` 9/9。
- 后端安全/恢复修复：登录无 Content-Length 时逐chunk限制16KiB；所有 `/api` 成功响应 `Cache-Control:no-store`；SQLAlchemyError统一安全503；恢复前WAL checkpoint，备份严格核对当前Alembic版本、完整SQLAlchemy schema签名和foreign_key_check；已有当日备份轮换失败安全重试，同worker日期只完整校验一次。
- 数据/来源修复：固定分类代码在写边界校验唯一顺序；动态未知地区/品类400；公开列表以SafeClient final_url解析相对链接；合法空feed与全无效响应用有界skip摘要区分；图片URL/署名成组且只由first_entry更新，证据/配置的image hosts与selection必须一致，撤销或主机收窄清图并更新updated_at；矛盾probe拒绝；入口失败在提交后记录安全 `entry_failed` 事件。
- Canonical 修复：补实际共享文件到 backend-012/022/032 Files，I09/I16/I20/I22/I31/I32 与实现同步，设计review记录已确认的有条件通过，coverage/上下文的“0完成”改为生成时事实，移除本机Playwright绝对路径。任务 owner 完成数仍为38/64，不因commit review修复增加任务完成数。
- 最终本地验证（本轮修复后的同一工作树）：backend `pytest` 232/232，通过 `compileall` 与 `pip check`；frontend unit 41/41、`typecheck`、`build`、`check:artifact`、`source-check` 全部退出0，build identity仍为 `d96594b5b586fae7127c15174648cd7f5bed87ebd1255b79003382bb5ce00ea2`，`runtimeVisualReviewed:false`。Linux/Compose/HTTPS、真实来源、07:30、生产视觉与真实E2E仍未验证，继续保持对应owner未完成。
- 提交前结构复核后，用户在 `backend-design-split-migration` 明确批准后端设计 small→split 迁移；内容按决策/架构、对象/数据、状态/接口、风险/验证四个完整语义片段转移，删除旧 small 文件并更新全部引用。前端设计仅补记这项授权，获批视觉来源 R-S hash 同步为 `349e1a0ec2fa01ccf17ba8053cd5cfb53824289fed49f9a41a750ea9047ebec2`，随后 `source-check` 与 `check:artifact` 均退出0。
- 更正上一条结构记录：`42,626` 是UTF-8字节数，原后端设计约22,000 Unicode字符并未超30,000字符硬限。告知纠正后，用户在 `confirm-backend-design-form-after-correction` 明确选择“恢复 small（Recommended）”；最终仅保留 `design/backend.md`，删除临时split目录并恢复所有引用。前端授权说明随之更新，最终 R-S hash 为 `e4f9c5c6aae0a2ba4df88416e2a8613ca933d8891a70f389effe8bf56af8b340`；API-R1 hash 同步为 `48f646ebec8bf384df2d8213194c033da4c266d5abe99bcb4c8d8d560d34ad32`。
- 最终small快照重新全量验证：backend `pytest` 232/232、`compileall`、`pip check`；frontend unit 41/41、`typecheck`、`build`、`check:artifact`、`source-check` 全部退出0，build identity仍为 `d96594b5b586fae7127c15174648cd7f5bed87ebd1255b79003382bb5ce00ea2`，`runtimeVisualReviewed:false`。两份历史research文档的尾随空格已清理，待精确暂存后由 `git diff --cached --check` 覆盖。
- 最终只读 small 审查又发现两处路径残留：`worker.py` 的 `fp-debt` 已改指现存 `fp-docs/changes/beauty-intelligence-mvp/design/backend.md#风险迁移发布回滚与监控`；恢复手册的 Alembic 配置路径已与 backend-038 既定 `WORKDIR /srv/app` 对齐为 `/srv/app/alembic.ini`。修复后 `compileall`、`pip check`、`git diff --check` 及 CodeGraph sync 退出0；运行逻辑和38/64完成数未改变。
