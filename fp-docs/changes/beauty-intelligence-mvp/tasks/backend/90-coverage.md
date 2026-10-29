## Coverage Matrix

Verification 中的 pytest 节点都以仓库根执行 `cd backend && python -m pytest <节点> -q`；真实验收节点另加 `--live`。本文生成时这些均为未来命令；当前哪些测试已实际运行只能由 owner checkbox、Git 与 `.fp-execute/progress.md` 证明，未完成 live 节点仍不得视为通过。覆盖来源：[proposal](<../../proposal.md>)、[backend design](<../../design/backend.md>)。

### Proposal 覆盖

| Source | Requirement / Boundary | Tasks | Verification |
| --- | --- | --- | --- |
| proposal P-001 | 单人登录、无注册/团队 | backend-006–backend-008, backend-040 | `tests/integration/api/test_auth_api.py::test_first_login_and_write_guards` |
| proposal P-002 | 标题浏览、查找、出处与收藏闭环；前端滚动/详情关闭不属后端 | backend-009–backend-014, backend-041 | `tests/integration/api/test_articles_api.py::test_article_contract_and_filters` |
| proposal P-003 | 七类、多类与未分类可读 | backend-010–backend-012 | `tests/unit/domain/test_classification.py::test_explicit_multilingual_rules` |
| proposal P-004 | 固定来源，禁止来源编辑 | backend-015, backend-016, backend-033–backend-037 | `tests/integration/persistence/test_sources.py::test_entry_evidence_is_not_site_permission` |
| proposal P-005 | 北京时间07:30、手动刷新/重试、部分失败/无新增/首次空库分别反馈 | backend-023–backend-030, backend-042 | `tests/integration/persistence/test_schedule.py`；`tests/integration/api/test_jobs_api.py` |
| proposal P-006 | 同链接去重、不同媒体不合并 | backend-009, backend-033 | `tests/integration/persistence/test_upsert.py::test_identity_and_reliable_merge` |
| proposal P-007 | 来源报道日期，可空、不补造 | backend-011, backend-019, backend-020 | `tests/integration/persistence/test_queries.py::test_filters_order_and_page_movement`；`tests/unit/infrastructure/test_parsers.py` |
| proposal P-008 | 无模型、摘要、正文与技术信息提炼 | backend-019–backend-022, backend-040, backend-044 | `tests/unit/infrastructure/test_parsers.py::test_rss_metadata_only`；`tests/acceptance/test_live.py::test_live_audit --live` |
| proposal P-009 | 收藏引用、元信息跟随、重启持久、取消不删、失败保留 | backend-009, backend-013, backend-014, backend-030, backend-041 | `tests/integration/persistence/test_bookmarks.py::test_persistent_reference_and_order`；`tests/integration/api/test_bookmarks_api.py::test_state_consistency_and_write_failure` |
| proposal P-010 | 图片仅允许外链、失败不影响文字/收藏、无下载代理 | backend-021, backend-039, backend-044 | `tests/integration/persistence/test_ingest.py::test_images_are_links_with_permission`；`tests/acceptance/test_live.py::test_live_audit --live`；浏览器图像降级由前端owner验收 |
| proposal P-011 | 排除团队/收费/全文/管理/导出/推送等 | backend-001, backend-040, backend-044 | `tests/integration/api/test_security_audit.py` |
| proposal P-012 | 绿地工程，不导入旧原型/虚构数据 | backend-001–backend-005, backend-038, backend-041 | `tests/integration/persistence/test_schema.py::test_full_upgrade_downgrade`；`tests/unit/infrastructure/test_deployment.py` |
| proposal P-013 | 真实可用个人MVP，非纯演示 | backend-041–backend-045 | `tests/acceptance/test_release.py::test_backend_release --live` |
| proposal P-014 | 只读保留small上游提案；本端任务按自身体积选形，不擅改PRD/提案 | backend-045；本轮结构自审 | `tests/acceptance/test_release.py::test_backend_release --live`；最终核对上游XOR与写入范围 |
| proposal P-015 | 明确栏目/标题规则，无信息不补造地区/品类 | backend-010 | `tests/unit/domain/test_classification.py::test_explicit_multilingual_rules` |
| proposal P-016 | 仅标题、来源、链接、可得日期和获许可图片 | backend-019–backend-022, backend-044 | `tests/unit/infrastructure/test_parsers.py`；`tests/integration/persistence/test_ingest.py` |

### Backend Design 决策覆盖

| Source | Requirement / Boundary | Tasks | Verification |
| --- | --- | --- | --- |
| design D-002 | 常开单台云服务器，真实运行 | backend-038, backend-039, backend-041 | `tests/unit/infrastructure/test_deployment.py`；`tests/acceptance/test_live.py::test_live_source --live` |
| design D-003 | 单人密码无注册 | backend-006, backend-008, backend-040 | `tests/unit/application/test_password.py::test_argon_and_limits`；`tests/integration/api/test_auth_api.py` |
| design D-004 | Python/FastAPI可导入工程 | backend-001, backend-038 | `tests/integration/api/test_bootstrap.py::test_factory_and_safe_errors` |
| design D-006 | SQLite单机持久、FK、短写事务 | backend-002–backend-005, backend-030 | `tests/integration/persistence/test_schema.py`；`tests/integration/runtime/test_recovery_integration.py` |
| design D-007 | 独立串行进程、数据库任务 | backend-004, backend-023, backend-025, backend-026 | `tests/integration/runtime/test_worker.py::test_serial_claim_and_partial_results` |
| design D-008 | 不接模型、不正文/摘要 | backend-019–backend-022, backend-044 | `tests/unit/infrastructure/test_parsers.py::test_rss_metadata_only`；`tests/acceptance/test_live.py::test_live_audit --live` |
| design D-009 | 仅必要元信息/可空日期/许可图片 | backend-003, backend-019–backend-022 | `tests/integration/persistence/test_ingest.py` |
| design D-010 | URL幂等，不做语义归并 | backend-009 | `tests/integration/persistence/test_upsert.py::test_identity_and_reliable_merge` |
| design D-011 | 栏目/明确多语词分类、未知保留 | backend-010, backend-011 | `tests/unit/domain/test_classification.py`；`tests/integration/persistence/test_queries.py` |
| design D-012 | RSS优先、获许可公开列表补充 | backend-019, backend-020, backend-033–backend-037 | `tests/unit/infrastructure/test_parsers.py`；`tests/integration/source_verification/test_verification.py` |
| design D-013 | 五站，PR TIMES两入口同站去重 | backend-015, backend-033–backend-037 | `tests/integration/persistence/test_sources.py::test_six_entries_start_disabled`；`tests/integration/source_verification/test_verification.py` |
| design D-014 | 逐站逐入口核验启用、受限不绕过 | backend-016, backend-033–backend-037 | `tests/integration/persistence/test_sources.py::test_entry_evidence_is_not_site_permission` |
| design D-015 | Linux+Docker Compose | backend-038, backend-039 | `tests/unit/infrastructure/test_deployment.py`；`sh deploy/compose.sh deploy/.env docker-compose.yml config --quiet` |
| design D-016 | 当天一次catchup，不追多日 | backend-028, backend-029, backend-042 | `tests/integration/persistence/test_schedule.py::test_missing_partial_and_restarts`；`tests/acceptance/test_live.py::test_live_schedule --live` |
| design D-017 | 服务端会话，退出立即失效 | backend-005, backend-007, backend-008 | `tests/integration/persistence/test_sessions.py::test_expiry_csrf_and_revoke` |
| design D-018 | 同域HTTPS | backend-008, backend-039, backend-041 | `tests/unit/infrastructure/test_deployment.py::test_compose_builds_one_dockerfile_and_exposes_only_gateway`；`tests/integration/api/test_static_frontend.py`；`tests/acceptance/test_live.py::test_live_source --live` |
| design D-019 | 每日一致性备份，七份与确认后恢复 | backend-031, backend-032, backend-043 | `tests/integration/persistence/test_backup.py`；`tests/acceptance/test_live.py::test_live_restore --live` |
| design D-021/D-038 | FastAPI静态资源+SPA、Caddy反代/TLS、单Dockerfile | backend-039, backend-041 | `tests/unit/infrastructure/test_deployment.py::test_compose_builds_one_dockerfile_and_exposes_only_gateway`；`tests/integration/api/test_static_frontend.py`；`tests/acceptance/test_live.py::test_live_source --live` |
| design D-022 | 七表字段、约束、SQLAlchemy/Alembic、索引/JSON | backend-002–backend-005 | `tests/integration/persistence/test_schema.py::test_full_upgrade_downgrade`；`tests/integration/persistence/test_schema.py::test_job_partial_indexes` |
| design D-023 | refresh全enabled、retry只失败/中断 | backend-023, backend-024 | `tests/integration/persistence/test_jobs.py::test_retry_only_unsuccessful_eligible_entries` |
| design D-024 | REST/JSON、分页、布尔收藏、最小任务契约 | backend-008, backend-011, backend-012, backend-014, backend-016, backend-025 | `tests/integration/api/test_articles_api.py`；`tests/integration/api/test_bookmarks_api.py`；`tests/integration/api/test_jobs_api.py` |
| design D-026 | 24h、Origin/CSRF、Argon2id、SSRF、负向与真实验收 | backend-006–backend-008, backend-017, backend-018, backend-040, backend-044 | `tests/integration/api/test_auth_api.py`；`tests/unit/infrastructure/test_safe_http.py`；`tests/integration/api/test_security_audit.py` |
| design D-027 | 只去空格与#，不删查询参数 | backend-009 | `tests/integration/persistence/test_upsert.py::test_identity_and_reliable_merge` |
| design D-028 | 至少一来源许可及真实更新成功 | backend-033–backend-037, backend-041, backend-045 | `tests/acceptance/test_live.py::test_live_source --live`；`tests/acceptance/test_release.py::test_backend_release --live` |
| design D-029 | 两端设计small与直接索引；任务形式独立选择 | backend-045；本轮结构自审 | `tests/acceptance/test_release.py::test_backend_release --live`；核对design end index与两small表示 |
| design D-030 | 中断保留成功项，只补未完成/失败；每天一次 | backend-026–backend-030, backend-042 | `tests/integration/runtime/test_recovery_integration.py::test_reading_survives_interrupted_update` |
| design D-031 | 首页报道日期倒序；收藏创建时间倒序，同时间ID倒序 | backend-003, backend-011, backend-013 | `tests/integration/persistence/test_queries.py`；`tests/integration/persistence/test_bookmarks.py::test_persistent_reference_and_order` |
| design D-032 | 首登无需旧CSRF但仍Origin/JSON/限流；其它写全保护 | backend-006–backend-008, backend-040 | `tests/integration/api/test_auth_api.py::test_first_login_and_write_guards` |
| design D-033 | 当天无记录catchup取当前已核验启用入口 | backend-029, backend-042 | `tests/integration/persistence/test_schedule.py::test_missing_partial_and_restarts` |
| design D-034 | 旧running先终结释放；pending不一概作废 | backend-027, backend-030, backend-042 | `tests/integration/runtime/test_worker.py::test_restart_settles_running_not_pending` |
| design D-035 | 各入口状态/原因/依据；网站仅汇总 | backend-002, backend-015, backend-016, backend-033–backend-037 | `tests/integration/persistence/test_sources.py::test_entry_evidence_is_not_site_permission` |
| design D-036 | 所有条目列表/详情bool与收藏写结果一致 | backend-011–backend-014 | `tests/integration/api/test_bookmarks_api.py::test_state_consistency_and_write_failure` |
| design D-037 | 普通page分页，接受更新跨页位移 | backend-011, backend-012 | `tests/integration/persistence/test_queries.py::test_filters_order_and_page_movement` |

D-001、D-005、D-020、D-025 的详细owner属于前端设计；这里不读取、复制或推断其task ID。后端提供稳定契约，浏览器页面、滚动保留、图像降级和视觉验收由主调度对接前端owner。

### Backend Boundary Checks

| Source | Requirement / Boundary | Tasks | Verification |
| --- | --- | --- | --- |
| Backend boundary | 七模型/四步迁移、FK、部分唯一、UTC和空库往返 | backend-002–backend-005 | `tests/integration/persistence/test_schema.py` |
| Backend boundary | application modules：URL合并、规则、查询、收藏与可恢复事务 | backend-009–backend-014, backend-022, backend-030 | `tests/integration/persistence/test_upsert.py`；`tests/integration/persistence/test_queries.py`；`tests/integration/persistence/test_bookmarks.py`；`tests/integration/runtime/test_recovery_integration.py` |
| Backend boundary | schema/serializer：JSON白名单、NULL、分页、错误包 | backend-001, backend-011, backend-012, backend-025 | `tests/integration/api/test_bootstrap.py`；`tests/integration/api/test_articles_api.py`；`tests/integration/api/test_jobs_api.py` |
| Backend boundary | FastAPI handlers/router与命名注册 | backend-008, backend-012, backend-014, backend-016, backend-025 | `tests/integration/api/test_security_audit.py::test_all_routes_protected_and_redacted` |
| Backend boundary | 权限映射：session读，session+Origin+CSRF写，首登特例 | backend-006–backend-008, backend-040 | `tests/integration/api/test_auth_api.py`；`tests/integration/api/test_security_audit.py` |
| Backend boundary | 固定来源两种解析分支和静态key，不建动态插件/IAM后台 | backend-015, backend-019, backend-020, backend-033–backend-037 | `tests/integration/persistence/test_sources.py`；`tests/unit/infrastructure/test_parsers.py`；`tests/integration/source_verification/test_verification.py` |
| Backend boundary | 外部client：DNS固定/TLS/重定向/大小/超时/许可图片 | backend-017–backend-022 | `tests/unit/infrastructure/test_safe_http.py`；`tests/integration/persistence/test_ingest.py` |
| Backend boundary | 异步任务与定时生命周期、并发、恢复、零新增 | backend-023–backend-030 | `tests/integration/persistence/test_jobs.py`；`tests/integration/runtime/test_worker.py`；`tests/integration/persistence/test_schedule.py` |
| Backend boundary | 集成/导入/权限负向/持久化失败 | backend-030, backend-038, backend-040 | `tests/integration/runtime/test_recovery_integration.py`；`tests/integration/api/test_security_audit.py` |
| Backend boundary | 备份恢复/迁移前置/同域发布/真实来源与错误可见 | backend-031, backend-032, backend-039, backend-041–backend-045 | `tests/integration/persistence/test_backup.py`；`tests/acceptance --live` |
| Engineering quality | 公共职责docstring、非显然事务/许可/DNS注释，简化不减验收 | backend-001–backend-045 | 每项GREEN后自审；`tests --ignore=tests/acceptance`与`tests/acceptance --live`；人工源码review不能被测试替代 |

### 规划自审结论

- 已逐项覆盖 proposal P-001–P-016 及后端设计的33条终态决策。没有发现未设计的后端需求；Design gap 清单为空。前端独有行为不伪造后端任务。
- 本端只有split入口，context/interface/coverage分别单一owner，10个tasks片段各自唯一拥有任务体；45项连续，当前完成度只从task body唯一checkbox与双端overview派生。
- 同端依赖都指向既有较早 ID，无环。主调度已核对 [frontend-001](<../frontend/10-foundation-tasks.md#L5-L58>) 的真实任务 owner 和 `frontend/dist` 产物，并将它加入 backend-039 的 Depends on；不是推测前端 ID。两端完整图及跨端边须在前端计划生成后再核验，不只在 overview 中增加隐式依赖。
- 代码片段、HTTP字段和任务Interfaces已经对齐唯一账本。单测fixture全部有创建owner；get_db、运行属性绑定、列表结构验证、可选result_id同事务提交、可信网关地址和DNS超时均已明确。发现的分类冲突覆盖、首登片段变量与恢复日志缺口已直接修正。
- 结构检查仅验证文档形式、大小、任务字段/步骤、ID、依赖、占位词与代码片段语法；不声称实现、依赖安装、单测、来源许可、目标云服务、证书或真实验收已通过。
- 规划生成时每个源码文件均为未来新建；当前存在性和验证状态须从源码、Git 与progress实时核对。生产/云资源、域名/DNS、80/443、私密摘要/CSRF密钥、来源许可、维护与恢复授权仍是对应真实任务前提；没有这些前提就保持owner未完成，不降级交付门槛。
