## Backend Interface Ledger

本文件是公共字段、内部符号、provider key 和生命周期的唯一详细 owner。任务的 Interfaces 引用下列 key；不得另造同义字段或未登记 helper。实现片段展示关键结构，不要求把同一契约重复贴进每个任务。

| Interface | Owner Task | Contract | Consumers | Verification |
| --- | --- | --- | --- | --- |
| I01 bootstrap | backend-001 | `Settings.from_environment()`、`create_app(settings=None)`、`ApiError(code,message,status)`、`install_errors(app)`；app.state.now为可注入UTC时钟，配置与 request_id 见下文 | 全部 API/worker | `test_bootstrap.py::test_factory_and_safe_errors` |
| I02 source models | backend-002 | `Base, Source, SourceEntry`；`make_engine(url)` 开 FK/busy timeout；`db_session(engine)`上下文；`get_db(request)->Iterator[Session]`按请求yield/rollback/close，db.info挂rules_config/source_config路径；迁移 0001 | 来源、条目、任务 | `test_schema.py::test_source_entry_constraints` |
| I03 article models | backend-003 | `Article, Bookmark`；迁移 0002；设计字段原样落表，JSON 分类合法与二进制 URL 唯一 | I09–I14 | `test_schema.py::test_article_bookmark_constraints` |
| I04 job models | backend-004 | `UpdateJob, EntryResult`；迁移 0003；活动/日程/补跑部分唯一索引、状态 CHECK、entry组合唯一 | I23–I30 | `test_schema.py::test_job_partial_indexes` |
| I05 session model | backend-005 | `Session`；迁移 0004；`token_digest` 唯一、UTC 时间；最终恰七表（不计 alembic_version） | I07 | `test_schema.py::test_full_upgrade_downgrade` |
| I06 password | backend-006 | `verify_password(password,encoded)->bool`，仅 Argon2id；`client_address(request,settings)->str`只信任精确网关peer的X-BI-Client-IP，否则用socket peer；`LoginLimiter.check(client_ip,now)`、`.failed(client_ip,now)`；超限抛 `ApiError('rate_limited',…,429)` | I08 | `test_password.py::test_argon_and_limits` |
| I07 sessions | backend-007 | `issue_session(db,settings,now)->(raw_token,AuthOut)`；`resolve_session(db,raw,settings,now)->Session`；`csrf_token(raw,key)->str`；`revoke_session(db,raw)`；过期/不存在401 | I08 | `test_sessions.py::test_expiry_csrf_and_revoke` |
| I08 auth API/guards | backend-008 | auth三路由；`LoginIn(password:str)`按HTTP表限值且forbid extra；`require_session`、`require_write` FastAPI dependencies；`require_origin(request,settings)`；`auth_router`；`mount_router(app,router)` 为 `include_router` 的直接使用，不建注册体系 | 全部业务路由 | `test_auth_api.py::test_first_login_and_write_guards` |
| I09 article write | backend-009 | `Headline` 不可变 dataclass，允许字段见下文；`dedup_url(url)->str`；`upsert_headline(db,h,now)->WriteResult(article_id,added,updated)`；写边界校验固定分类代码/去重/顺序，图片URL与署名成组更新且仅first_entry可改变；事务由调用者持有 | I22 | `test_upsert.py::test_identity_and_reliable_merge` |
| I10 classification | backend-010 | `Classification(category_codes,region,product_type)`；`CATEGORY_CODES`/`CATEGORY_LABELS`按下表固定顺序；`classify(title,section,rules)->Classification`；`load_rules(path)->list[Rule]`，Rule={field,pattern,value,evidence}，只支持category/region/product_type | I22 | `test_classification.py::test_explicit_multilingual_rules` |
| I11 query | backend-011 | `ArticleQuery(q,category,region,product_type,date_from,date_to,page=1,page_size=20)`；`parse_query(mapping)->ArticleQuery`；`list_articles(db,query,bookmarked_only=False)->ArticlePage`；`article_out(db,article)->ArticleOut`；`filter_options(db)->FiltersOut` | I12、I13 | `test_queries.py::test_filters_order_and_page_movement` |
| I12 reading API | backend-012 | `articles_router`；三 GET 路由 articles/list、articles/detail、filters；detail id 为正整数；筛选错误400 | 前端消费者 | `test_articles_api.py::test_article_contract_and_filters` |
| I13 bookmark logic | backend-013 | `set_bookmark(db,article_id,value,now)->BookmarkOut`；不存在404；存在则幂等，不重置 created_at；`list_bookmarks(db,query)->ArticlePage` | I14 | `test_bookmarks.py::test_persistent_reference_and_order` |
| I14 bookmark API | backend-014 | `bookmarks_router`；GET list、PUT/DELETE item；受保护写；存储失败503且回滚 | 前端消费者 | `test_bookmarks_api.py::test_state_consistency_and_write_failure` |
| I15 fixed registry | backend-015 | `load_registry(path)->list[EntrySpec]`；`seed_sources(db,specs)`；`bind_entry_spec(entry,spec)->SourceEntry`按(source_key,url)将key/hosts/selection/图片条件绑定到临时属性，不增加表字段；EntrySpec 见下文；仅静态 key `rss`/`public_list` 两解析分支，无动态 provider 装载 | I16、I22 | `test_sources.py::test_six_entries_start_disabled` |
| I16 verification/source API | backend-016 | `eligible_entries(db)->list[SourceEntry]`；`apply_verification(db,evidence,probe,now)`；`sources_out(db)->list[SourceOut]`；`sources_router`；`read_evidence(path)`、`write_evidence(path,report)`；allowed证据的image_hosts/image_allowed/selection须与I15固定配置一致，public_list必须有冻结selection；撤销或图片主机收窄时清除以first_entry_id归属的图片并更新updated_at；每入口读取后用I15绑定运行配置；核验CLI由I33创建，未许可不做probe | I23–I29、I33–I37 | `test_sources.py::test_entry_evidence_is_not_site_permission` |
| I17 target safety | backend-017 | `validate_target(url,allowed_hosts,resolve)->Target(host,port,path,ip)`；DNS resolver `(host,port)->list[str]`，生产用`resolve_bounded(host,port,timeout=5)`标准库子进程getaddrinfo，超时终止回收，不留无限线程；只允许全部地址均公网的 approved HTTPS443 主机；`BlockedTarget` | I18 | `test_safe_http.py::test_reject_reserved_and_rebinding` |
| I18 bounded transport | backend-018 | `SafeClient(allowed_hosts,resolve,dial,limits)`；`SafeClient.from_spec(entry)`构造生产resolver/dial/limits；`.fetch(url)->Fetched(final_url,media_type,body)`；dial(target,timeout)只连固定ip；TLS 使用 target.host；`FetchError(code,message)`；`Limits(connect=5,read=10,total=30,max_bytes=2097152,max_redirects=3)` | I22、I16 probe | `test_safe_http.py::test_pinned_redirect_and_limits` |
| I19 RSS parser | backend-019 | `parse_rss(raw,entry)->ParseBatch(headlines,skipped)`；defusedxml，支持 RSS2 与 RDF 标题/link/date/category；拒绝 DTD/实体；不读 description/content/summary；`ParseError` | I22 | `test_parsers.py::test_rss_metadata_only` |
| I20 list parser | backend-020 | `ListSelection(container,item,title,link,empty=None,date=None,section=None,image=None,credit=None,date_format=None)`；`parse_list(raw,entry)->ParseBatch`；固定入口 CSS 选择器，无脚本，无详情补取；I22将SafeClient已验证的final_url写入运行entry.url，作为相对标题/图片链接基准 | I22 | `test_parsers.py::test_public_list_has_no_detail_fetch` |
| I21 image boundary | backend-021 | `allowed_image(url,credit,entry)->(url\|None,credit\|None)`；许可证据的 image_allowed 且 allowlist HTTPS 主机才能保存；不发送网络请求 | I22 | `test_ingest.py::test_images_are_links_with_permission` |
| I22 ingestion | backend-022 | `ingest_entry(db,entry,client,now,result_id=None)->IngestResult(added,updated,skipped)`；复核 entry 条件，读取一次、白名单解析、分类与 upsert；若result_id给定，成功EntryResult/计数与条目同事务提交，非空skipped压成不含原始片段的有界error摘要，合法空feed保持error=null；失败无last_success变更；`safe_error(exc)->str` | worker | `test_ingest.py::test_entry_atomicity_zero_and_invalid_rows` |
| I23 enqueue | backend-023 | `enqueue_refresh(db,now)->EnqueueResult(job,reused)`；候选取 eligible_entries；先返回现有活动任务，否则创建 trigger=refresh 与结果；无入口409；`enqueue(db,trigger,entry_ids,schedule_date,now)`共享短事务入口 | I24、I25、日程 | `test_jobs.py::test_concurrent_refresh_reuses_active` |
| I24 retry | backend-024 | `retry_job(db,job_id,now)->EnqueueResult`；先校验 job存在；有活动则复用；只选原任务 failed/interrupted 且当前 eligible 的入口，无候选409 | I25 | `test_jobs.py::test_retry_only_unsuccessful_eligible_entries` |
| I25 jobs HTTP | backend-025 | `jobs_router`、`RefreshIn(trigger:Literal['refresh'])`；`job_out(db,job)->JobOut`；`current_job(db)->JobOut\|None`；路由current必须在动态id前注册 | 前端消费者 | `test_jobs_api.py::test_job_routes_and_null_current` |
| I26 worker | backend-026 | `claim_next(db,now)->UpdateJob\|None` 原子 pending→running；`process_job(db,job,client_factory,now_fn)`；`finish_job(db,job,now)`；`worker_loop(settings)`；`single_worker_lock(path)` 以 Linux flock 拒绝第二实例；`application_lease(path,exclusive=False)` 与恢复共享锁 | 日程/部署 | `test_worker.py::test_serial_claim_and_partial_results` |
| I27 settlement | backend-027 | `settle_interrupted(db,now)->int`，只能在持有 single_worker_lock 后启动时调用；running→interrupted，pending/running结果→interrupted；不覆盖成功/失败；先释放活动约束 | worker startup | `test_worker.py::test_restart_settles_running_not_pending` |
| I28 schedule | backend-028 | `schedule_due(db,now)->EnqueueResult\|None`；北京时间日期、07:30时刻；单日 schedule唯一，过了当日首轮/错过按I29处理；`tick(db,now)`先维护再调度 | worker loop | `test_schedule.py::test_beijing_0730_schedule` |
| I29 catchup | backend-029 | `catchup_due(db,now)->EnqueueResult\|None`；仅当日07:30之后、无活动且未用catchup；无schedule/无结果候选全部eligible，否则非成功交集；无可执行候选不耗次数 | worker tick | `test_schedule.py::test_missing_partial_and_restarts` |
| I30 recovery integration | backend-030 | 不新增公共生产接口；验证I22–I29；结算日志事件`job_interrupted`携job_id，入口存储失败`entry_failed`、备份失败`backup_failed`只带安全类型/ID；读取不被采集阻断，锁/满盘可见 | release | `test_recovery_integration.py::test_reading_survives_interrupted_update` |
| I31 backup | backend-031 | `backup_once(db_path,directory,now)->Path`；`daily_backup(db_path,directory,now)->Path\|None`；SQLite online backup、integrity_check、当前Alembic版本、完整schema签名与foreign_key_check后原子rename，最近7份；worker同日成功后只在内存记已验证日期，重启最多复核一次；失败保留旧份且安全日志 | worker tick | `test_backup.py::test_consistent_backup_and_rotation` |
| I32 restore | backend-032 | `restore_backup(backup_path,db_path,lease_path,confirmation)->Path`，返回pre-restore安全副本路径；exclusive lease、WAL checkpoint、完整schema校验、先保留当前库、原子替换；CLI `python -m app.backup restore --backup <path> --database <path> --lease <path> --confirm '已确认损失备份后的写入'` | ops | `test_backup.py::test_restore_requires_stop_and_confirmation` |
| I33–I37 site evidence | backend-033–backend-037 | I33创建`verify_entry(db,spec,evidence,now)->dict`与CLI `python -m app.sources verify --entry <entry-key> --evidence <file> --probe`；spec是I15绑定后的SourceEntry；其余站点复用I16/I33；证据JSON见下文；review可以结论pending/restricted，不能把无法确认写allowed | source gate | `test_verification.py::test_prtimes`、`test_happi`、`test_qingyan`、`test_pbn`、`test_cosin` |
| I38 runtime | backend-038 | 镜像 API 命令 `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers`；worker命令 `python -m app.worker`；工厂无参时从环境构造Settings | Compose | `test_deployment.py::test_shared_image_and_commands` |
| I39 gateway | backend-039 | 三服务 caddy/api/worker，前端产物 `frontend/dist` 为外部消费契约；Caddy /api/* 原样转发，静态SPA fallback；API只内网，清除外来代理头后设可信客户端地址 | 前端构建、live | `test_deployment.py::test_same_origin_compose_contract` |
| I40 security | backend-040 | 不增路由；测试专用`audit_route_guards(client)->dict[path,status]`枚举实际受保护GET并真实请求，另外参数化全部写保护；核验读401、写401/403、登录不误要CSRF、脱敏/导入无联网 | release | `test_security_audit.py::test_all_routes_protected_and_redacted` |
| I41–I45 acceptance | backend-041–backend-045 | `capture_live_source(env)`、`capture_schedule(env)`、`capture_restore(env)`、`capture_audit(env)`、`release_report(paths)` 为 test_live/test_release 内测试辅助函数，不进入应用；仅 --live 授权运行 | 发布门禁 | `acceptance/test_live.py`、`acceptance/test_release.py` |
| T01 test fixtures | backend-001–backend-008 | `now`固定UTC可替换；`settings`使用测试Argon摘要与私密key；`client` HTTPS TestClient且raise_server_exceptions=False，依赖覆盖到同一个db；`db`临时文件SQLite Session；`entry_factory(**overrides)`默认pending禁用，附I15运行属性；`article_factory(**overrides)`自动来源/入口并提交；`job_factory(**overrides)`支持entry_ids/result_states，自动填合法started/finished/schedule_date，生成显式job.entries关系并提交；`user_client`登录后的client，含Origin和CSRF头 | 全部离线测试 | 各自 owner 测试 |
| T02 network/worker labs | backend-018、backend-026 | `http_lab.reply(url,status=200,headers={},body=b'')`、resolve/dial、connections和`client_for(entry)`提供逐连接日志及可控响应；`worker_lab`复用db并提供other_db、client_factory、now()、after_0730、pending_job(entries)、succeed(index,title,url)、fail(index,code)、article(bookmarked)、running_job(result_states)（默认当日schedule）、pause_network()、start_paused_job(id)、crash_and_reopen()；暂停/崩溃使用真实独立连接/进程，网络只模拟元信息 | 出站/恢复测试 | I18、I26 测试 |
| T03 acceptance fixtures | backend-033、backend-041 | `verification_files(source_key)`实际读取verification/<key>.json并校验SiteEvidence，不伪造已获许可；`live_env`只在`--live`且明确目标/授权时启用，其字段origin/environment/password(仅内存)/schedule_observation/restore_observation/restored_copy/audit_observation/readonly_db来自显式环境输入；pytest_addoption登记--live、pytest mark live；缺条件UsageError；默认套件显式排除acceptance，不把跳过算通过 | live tasks | I33–I45 测试 |

### 数据结构和枚举

```python
# Headline 是入口解析后的白名单值对象，不含正文或原始响应。
@dataclass(frozen=True)
class Headline:
    source_id: int
    first_entry_id: int
    original_url: str
    title: str
    reported_date: date | None = None
    category_codes: tuple[str, ...] = ()
    region: str | None = None
    product_type: str | None = None
    image_url: str | None = None
    image_credit: str | None = None
    section: str | None = None  # 仅供明确规则使用，不持久化全文。

# Settings 是显式 dataclass，从 os.environ/私密挂载文件构造，不另装配置框架。
# 字段：database_url, public_origin, password_hash, csrf_key, source_config,
# rules_config, data_dir, backup_dir, trusted_gateway_ip；其余受限默认值见Global Constraints。
# EntrySpec 字段：key(配置内稳定键，不新增DB列), source_key, source_name,
# language, url, kind, allowed_hosts, image_hosts, image_allowed,
# verification_status, verification_reason, verification_reference, enabled,
# selection(ListSelection\|None)；运行时用(source_id,url)定位既有SourceEntry。
```

| 名称 | 精确值与语义 |
| --- | --- |
| CategoryCode | `new_products` 新品发布；`trends` 趋势洞察；`new_ingredients` 新原料；`research_technology` 研发技术；`packaging_formulation` 包装与剂型；`oem_odm` OEM／ODM；`regulation_compliance` 法规与合规 |
| 筛选缺值 | category=`__uncategorized__`；region/product_type=`__unknown__`。不是存库值；分别匹配空数组或NULL。region/product_type其余值只消费 filters 动态返回，不发明固定市场枚举 |
| EntryKind | `rss`、`public_list` |
| VerificationStatus | 入口：`pending`、`allowed`、`restricted`；网站汇总：全部allowed→`allowed`，部分allowed→`partial`，无allowed且有pending→`pending`，全部restricted→`restricted`；状态不表示当次网络成功 |
| JobTrigger | `schedule`、`catchup`、`refresh`、`retry`；API refresh 对应手动，内部schedule/catchup不可由请求伪造 |
| JobState | `pending`、`running`、`succeeded`、`partial`、`failed`、`interrupted` |
| EntryResultState | `pending`、`running`、`succeeded`、`failed`、`interrupted` |
| SkipReason | `missing_title`、`missing_url`、`unsafe_url`、`field_too_long`、`invalid_date`；invalid_date保留条目但日期为空，其余缺关键项跳过；计入可显示错误摘要，不保存原始片段 |
| ArticleQuery | 单值q/category/region/product_type/date_from/date_to/page/page_size；日期含边界；date_from>date_to、非法category或页码、重复单值参数均400；q按NFKC+casefold且作字面包含匹配，`%`/`_`不作为SQL通配符 |

### HTTP 字段和返回状态

```text
ErrorOut = {code: str, message: str, request_id: str}
AuthOut = {authenticated: true, expires_at: UTC timestamp, csrf_token: str}
SourceRef = {id: int, key: str, name: str, language: str|null}
ArticleOut = {id: int, title: str, source: SourceRef, original_url: str,
 reported_date: YYYY-MM-DD|null, category_codes: CategoryCode[], region: str|null,
 product_type: str|null, image_url: str|null, image_credit: str|null,
 updated_at: UTC timestamp, bookmarked: bool}
ArticlePage = {items: ArticleOut[], total: int, page: int, page_size: int}
FiltersOut = {categories: [{value: CategoryCode, label: str}],
 regions: [{value: str, label: str}], product_types: [{value: str, label: str}],
 uncategorized_value: '__uncategorized__', unknown_value: '__unknown__'}
BookmarkOut = {article_id: int, bookmarked: bool}
EntryOut = {id: int, url: str, kind: EntryKind,
 verification_status: VerificationStatus, verification_reason: str|null,
 verification_reference: str|null, enabled: bool, last_success_at: UTC|null,
 last_error: str|null}
SourceOut = {id: int, key: str, name: str, language: str|null,
 verification_status: 'pending'|'allowed'|'partial'|'restricted', reason: str|null,
 entries: EntryOut[]}
EntryResultOut = {entry_id: int, source_id: int, source_name: str, entry_url: str,
 state: EntryResultState, count_added: int, count_updated: int,
 error: str|null, finished_at: UTC|null}
JobOut = {id: int, trigger: JobTrigger, state: JobState, schedule_date: YYYY-MM-DD|null,
 created_at: UTC, started_at: UTC|null, finished_at: UTC|null,
 count_added: int, count_updated: int, entries: EntryResultOut[]}
# 顶层计数=sum(已提交的entries计数)；不新增库字段。
EnqueueOut = {job: JobOut, reused: bool}
CurrentJobOut = {job: JobOut|null}
```

| Method / URL / route name | Request | Success | Error / auth / owner |
| --- | --- | --- | --- |
| POST `/api/auth/login` `auth_login` | `{password:str}`（1–1,024字符、禁止extra、body≤16 KiB）、精确Origin、Content-Type application/json；不消费CSRF | 200 AuthOut + Secure Cookie | 400 bad_request，403 origin_denied，415 json_required，401 invalid_credentials，429 rate_limited；backend-008 |
| GET `/api/auth/session` `auth_session` | Cookie | 200 AuthOut | 401 unauthenticated；backend-008 |
| POST `/api/auth/logout` `auth_logout` | `{}`、Cookie/Origin/CSRF | 200 `{authenticated:false}`，清Cookie并撤销 | 401/403；backend-008；无会话重复退出401但无副作用 |
| GET `/api/articles` `article_list` | ArticleQuery | 200 ArticlePage | 400 invalid_filter，401；backend-012 |
| GET `/api/articles/{id}` `article_detail` | 正整数id | 200 ArticleOut | 400 bad_request，404 article_not_found，401；backend-012 |
| GET `/api/filters` `filter_options` | 无 | 200 FiltersOut | 401；backend-012 |
| GET `/api/bookmarks` `bookmark_list` | ArticleQuery | 200 ArticlePage，全部bookmarked=true | 400 invalid_filter，401；backend-014 |
| PUT `/api/bookmarks/{article_id}` `bookmark_put` | `{}`、Cookie/Origin/CSRF | 200 BookmarkOut(true) | 404 article_not_found，401/403，503 storage_unavailable；backend-014 |
| DELETE `/api/bookmarks/{article_id}` `bookmark_delete` | 无body、Cookie/Origin/CSRF | 200 BookmarkOut(false) | 同上；backend-014 |
| GET `/api/sources` `source_list` | 无 | 200 `{items:SourceOut[]}`，五站及全部候选入口 | 401；backend-016 |
| POST `/api/update-jobs` `job_create` | `{trigger:'refresh'}`、Cookie/Origin/CSRF | 新建202 EnqueueOut(reused=false)，复用活动200 EnqueueOut(true) | 400 invalid_trigger，409 no_enabled_sources，401/403；backend-025 |
| POST `/api/update-jobs/{id}/retry` `job_retry` | `{}`、Cookie/Origin/CSRF | 新建202或复用200 EnqueueOut | 404 job_not_found，409 no_retryable_entries，401/403；backend-025 |
| GET `/api/update-jobs/current` `job_current` | 无 | 200 CurrentJobOut；活动优先，否则最近created_at/id，完全无记录null | 401；backend-025 |
| GET `/api/update-jobs/{id}` `job_detail` | 正整数id | 200 JobOut | 404 job_not_found，401；backend-025 |

所有受保护业务操作权限只有 `session`（读取）或 `session+origin+csrf`（写入），无角色、IAM action后台或额外权限枚举。无会话401 `unauthenticated`，Origin错误403 `origin_denied`，CSRF缺失/不符403 `csrf_invalid`。RequestValidationError统一400 `bad_request`或查询解析的`invalid_filter`，不泄露输入；login body超16 KiB为413 `request_too_large`。数据库暂不可用503 `storage_unavailable`；框架404/405为`not_found`/`method_not_allowed`，未知500为`internal_error`，都用ErrorOut。无来源、图片、正文、模型或用户管理写路由。

### 逐入口核验和验收证据

```text
SiteEvidence = {source_key, reviewed_at: UTC, environment: str,
 entries: [{entry_key, url, verification_status, verification_reason,
 verification_reference, terms_checked_at: UTC, automation_allowed: bool|null,
 title_storage_allowed: bool|null, image_allowed: bool, image_hosts: str[],
 selection: ListSelection|null, probe: {attempted: bool, succeeded: bool,
 checked_at: UTC|null, title_count: int, final_url: str|null, error: str|null}}]}
# allowed要求自动读取/标题保存均明确true、原因/依据完整；enabled再要求目标环境probe成功。
# 许可不明使用pending且disabled；明确禁止用restricted且disabled。
# 图片许可可以false；不妨碍无图标题入口启用。
LiveEvidence = {checked_at: UTC, environment: str, origin: HTTPS URL,
 passed: bool, checks: [{name: str, passed: bool, evidence: str}]}
# evidence记录可复查的任务ID/状态/时间/计数或条款引用，不记录Cookie、口令或原始正文。
```

CLI 不接受任意新增站点：entry-key 必须是固定配置六项之一。JSON 中的 evidence/probe 只能由实际检查生成；测试不能填入假时间或假许可作为正式证据。I33–I37 的本地结构测试可以通过，但 I41–I45 必须在真实环境运行，不能由离线测试替代。
