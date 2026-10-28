# 标题版美妆情报台 Backend Implementation Plan

> **For agentic workers:** REQUIRED FLOW: Use `fp-execute` to implement this plan task-by-task. Only task markers use checkbox syntax for tracking; substeps are plain ordered instructions.

**Goal:** 交付单人登录、标题查找、出处导航、持久收藏和可恢复的真实来源更新。至少一个入口在目标云服务器通过许可与运行验收后，才允许宣称正式交付。

**Architecture:** 单台 Linux 主机、一个 FastAPI 实例、一个独立串行 worker、SQLite 持久卷；Caddy 提供同域 HTTPS 与静态资源。数据库持有更新任务，不引入 Redis、分布式队列或搜索服务。来源、分类、收藏、调度和备份属于同一阅读闭环，不是互不相关的子系统。

**Tech Stack:** Python + FastAPI、SQLAlchemy 2、Alembic、SQLite、Linux Docker Compose、Caddy；与已确认设计一致。规划生成时尚无正式工程或现成测试命令；当前实现、命令和证据必须从源码、Git 与执行记录实时核对。

## Global Constraints

- 已核验 [proposal](<../../proposal.md>) 与 [backend design](<../../design/backend.md>) 均为 small；提交前纠正字符数误判后，用户再次明确选择后端恢复 small。前端也保持 small，[design index](<../../design/00-index.md>) 与实际形式一致；没有旧设计路径、双形式或无索引目录，本端规划不复制前端设计细节。
- 规划生成时项目 manifest、后端 settings 和正式生产工程均缺失；当前信息层与 Code Standards 登记以 `fp-docs/manifest.md`、`fp-docs/settings/backend.md` 和当前源码为准。旧原型仍不得作为后端工程、真实数据或来源证据。
- 本端选 split。估算依据：45 个独立测试/review 边界，每个五步 TDD 任务至少约 40 行，仅任务体即约 1,800 行；加约 250 行上下文、接口与覆盖，超过 500 行。不是因为站点多而拆。直接写最终目录，不产生 small 文件。每片保持不超过 500 行、30,000 字符。
- 本计划生成时 45 个任务均未执行。每个 checkbox 只存在于所属 tasks 分片；当前完成度必须从唯一 owner checkbox、[双端 overview](<../00-overview.md>)、Git 和 `.fp-execute/progress.md` 实时核对。执行仍须遵守已确认 `fp-execute`、环境与真实证据门禁。
- 所有业务、测试和部署文件在规划时均为拟新建；执行后文件可能已经存在。后续任务中的 Extend planned 表示 owner 关系，不可用于判断当前文件缺失；消费者须读取当前源码。任何超出规划的新文件仍须先补进结构规划。
- 实现基线：Python 3.12；运行依赖 `fastapi>=0.115,<1`、`pydantic>=2,<3`、`uvicorn>=0.30,<1`、`SQLAlchemy>=2,<3`、`alembic>=1.13,<2`、`argon2-cffi>=23.1,<26`、`defusedxml>=0.7,<1`、`beautifulsoup4>=4.12,<5`；测试依赖 `pytest>=8,<10`、`httpx>=0.27,<1`。这些是工程可接受范围；实际解析版本以锁定/环境和 progress 证据为准，执行或复核时重新确认，不以规划范围代替兼容验证。运行出站使用标准库固定地址连接，不用默认会重新解析 DNS 的 HTTP client。
- **执行环境定点修订（用户本轮明确选择）**：先在当前 Windows 开发与运行可移植后端单元／接口测试；线上仍用 Linux＋Docker Compose 部署并完成 Linux 专属锁、恢复、真实来源、HTTPS 和 E2E 验证。Windows PASS 只证明对应可移植任务，不替代 Linux 专属行为。保留所有 backend-NNN、依赖和原设计；不将缺环境的任务跳过或标完成。
- 本计划测试命令默认仓库根目录执行，除非显式 `cd backend`。backend-001 使用已核验 Python 3.12 的 `venv` 建立仅本仓库的 `backend/.venv/`，在 Windows MSYS2 bash 中先 `export PATH="$(pwd)/backend/.venv/Scripts:$PATH"`，再运行规划中的 `python -m pip install -e './backend[test]'` 和 `cd backend && python -m pytest ... -q`；执行时用 `python -c 'import sys; print(sys.executable)'` 核对解析路径确实指向本仓库 venv，不得误用全局 conda。`backend/pyproject.toml` 设置 pytest `testpaths=['tests']`、`pythonpath=['.']`。将来 Linux 执行时重建 Linux venv/镜像并重跑任务要求的对应测试；`fcntl`／flock、真实 Compose/TLS/来源及恢复验收仅在可用 Linux 环境下通过。
- 单人密码仅以 Argon2id 摘要存于部署私密文件；不建用户或注册表。24 小时服务端会话，数据库仅存令牌摘要；CSRF 使用私密密钥对会话令牌做 HMAC。Cookie 名 `bi_session`，`HttpOnly; Secure; SameSite=Strict; Path=/`，不设 Domain。退出删除服务器记录；再次使用失效令牌为 401。
- 首登只验证精确本站 Origin、JSON、密码与限流，不要求已有 Cookie/CSRF；password为1–1,024字符、禁止额外字段、JSON body最多16 KiB。其它业务接口均需有效会话；写请求同时验证 Origin 和 `X-CSRF-Token`。无会话 401，Origin/CSRF 错误 403。错误包固定 `{code,message,request_id}`，不暴露正文、密码、Cookie、私密配置或堆栈。请求标识由服务端生成，不信任任意传入值。
- 登录默认每个直连代理确认后的客户端地址 15 分钟最多 5 次失败尝试，成功不消除其它未过期地址的计数；同时全局每分钟最多 30 次登录尝试。FastAPI 单实例内存计数，单次重启会重置，Caddy 不开放 API 直连端口；这是当前单实例安全配置，不声称分布式防爆破。生产启动拒绝缺少 PUBLIC_ORIGIN、密码摘要或 CSRF 密钥；不信任任意代理身份头。
- 时间戳存 UTC 并以 RFC 3339 `Z` 返回；日程日期与备份日按 `Asia/Shanghai`。报道日期为来源明示日期，不以采集、刷新或上市日期补造。首页 `reported_date DESC, id DESC`，NULL 在后；收藏 `created_at DESC, article_id DESC`。重复收藏不重置时间。
- 链接身份仅 `strip().split('#',1)[0]`，二进制精确比较；保留查询参数、参数顺序、路径和大小写。相同链接更新原条目，首次来源归属不变，缺失字段不抹掉可靠旧值；不同链接不合并。无正文、摘要、模型、跨媒体事件或内容历史。
- 搜索仅标题与来源。七分类多选数组，未知分类 `[]`，地区/品类/日期/图片可空；不从站点所在国推断市场。简单 page/page_size 默认 1/20，上限 100；允许后台更新引起跨页位移，不加快照或游标。过滤约定见唯一接口账本。
- SQLite 开启外键、5 秒 busy timeout；短事务、原子 claim 和部分唯一索引兜底。API 与 worker 共享文件卷，但只有一个 worker。一个活动任务；并发触发返回已有任务。任务计数只计算已提交的条目；原始响应和异常堆栈不进入数据库。
- 来源入口逐个保存 pending/allowed/restricted、原因、依据，网站层只汇总。仅入口允许、证据完整且目标环境运行验证成功后启用。许可判定与 last_error 分离；无来源编辑 HTTP API。PR TIMES 两入口同站去重；五站候选不等于五站已授权。
- 出站默认仅 HTTPS、443、已批准主机；每次 DNS 解析验证全部地址为公网并固定本次连接地址，TLS 保留原域名 SNI/证书验证。每次重定向重新验证；最多 3 跳、共 4 请求、无隐式重试；连接 5 秒、读取 10 秒、总预算 30 秒；原始响应上限 2 MiB，拒绝压缩响应，避免解压膨胀。超限/截断/解析错误不得记成功；正常零条可以成功。
- 字段边界：标题 1–1,000 字符，URL 4,096 字符，来源名称 200 字符，搜索 q 200 字符，地区/品类 100 字符，图片署名 500 字符，可展示错误 500 字符。超限条目跳过并累计理由，不截断 URL。缺标题或原文链接不得建条目；拒绝恶意协议和凭据 URL。
- 只解析 RSS 或经许可的公开列表，严禁文章详情抓取、执行网页脚本或绕过付费/防护。RSS 内文即使经过内存也不提取、不记日志、不存库。图片只保存经入口许可核验且主机允许的 HTTPS URL/署名，浏览器直接加载；不下载、代理、转存、内嵌或建立图片表。
- 07:30 后当天自动补跑最多一次。无当天 schedule/结果时候选为当前已核验启用入口；有记录只补未成功入口。创建 catchup 自身占用当天次数；不追多日。旧 running 先结算 interrupted 并填结束时间、释放活动占用，成功结果与条目保留；pending 不一概作废。之后才检查补跑或接受新任务。
- 每日 SQLite 在线一致性备份，最近七份，先校验并原子落盘再轮换。恢复必须停写、验证备份、明确确认损失窗口；本机备份不覆盖整机丢失。锁争用、磁盘满和备份失败要有安全可见日志，不能伪造成功。
- Engineering quality: 独立实现者与 reviewer 自行读取插件相对资源 `skills/_shared/engineering-quality.md`，并按 workspace contract 解析当前安装根。Python 公共对象使用准确中文 docstring；非显然权限、事务、DNS 固定、恢复与幂等边界说明原因。不开新注册/工厂体系。当前单串行 worker、SQLite 与非全文搜索的适用上限及重访条件唯一 owner 为已确认后端设计的风险章节；本计划不削减验收。
- 发布须有用户提供的 Linux 主机、域名/DNS、80/443、私密配置、来源使用条件证据与真实网络验证。无这些条件不能将云部署、许可或真实更新标为通过。Git commit、push 和 PR/MR 均须逐轮独立授权；当前是否已执行只能由 Git 和对应工作流证据确认。

## File Structure

以下均由计划中的首次 owner 以 create 动作负责；执行后文件可能已存在，须读取当前源码。表中逗号分隔的名称表示同一目录内各个精确文件，不表示 glob。

| Path | Action | Responsibility |
| --- | --- | --- |
| `backend/pyproject.toml` | create | 依赖范围、构建和 pytest 配置 |
| `backend/.gitignore` | create | 忽略 Windows 本仓库虚拟环境、Python 缓存与本地测试数据；不改动原型或全局设置 |
| `backend/app/__init__.py`、`backend/app/main.py` | create | 包标识与应用工厂 |
| `backend/app/config.py`、`backend/app/errors.py` | create | 私密配置校验、错误包和 request_id |
| `backend/app/database.py`、`backend/app/models.py` | create | SQLite 连接、七模型、约束、运行/恢复租约 |
| `backend/alembic.ini`、`backend/alembic/env.py` | create | Alembic 数据库入口 |
| `backend/alembic/versions/0001_sources.py` | create | 来源与入口表 |
| `backend/alembic/versions/0002_articles.py` | create | 条目与收藏表 |
| `backend/alembic/versions/0003_jobs.py` | create | 任务、入口结果、部分唯一索引 |
| `backend/alembic/versions/0004_sessions.py` | create | 会话表与完整 schema 校验 |
| `backend/app/auth.py`、`backend/app/api_auth.py` | create | 密码/限流/会话/写保护与登录路由 |
| `backend/app/articles.py`、`backend/app/api_articles.py` | create | URL 幂等写入、查询、DTO 与阅读路由 |
| `backend/app/classification.py`、`backend/config/classification.json` | create | 明确标题/栏目分类规则和证据 |
| `backend/app/bookmarks.py`、`backend/app/api_bookmarks.py` | create | 收藏关系与 API |
| `backend/app/sources.py`、`backend/app/api_sources.py` | create | 固定入口、证据校验、运行核验 CLI、只读 API |
| `backend/config/sources.json` | create | 五站六候选入口及逐入口许可/选择器/图片条件；初始全部禁用 |
| `backend/app/safe_http.py` | create | DNS 校验、固定地址 TLS、重定向/超时/大小预算 |
| `backend/app/parsers.py`、`backend/app/ingest.py` | create | RSS/公开列表白名单元信息、图片过滤、单入口采集 |
| `backend/app/jobs.py`、`backend/app/api_jobs.py` | create | 入队、重试、状态序列化与路由 |
| `backend/app/worker.py`、`backend/app/schedule.py` | create | 独立串行消费、中断结算和北京时间日程 |
| `backend/app/backup.py` | create | 一致性备份、轮换、独占离线恢复 CLI |
| `backend/tests/__init__.py`、`backend/tests/conftest.py` | create | 隔离数据库、HTTPS 测试客户端、时钟与通用 fixture |
| `backend/tests/test_bootstrap.py`、`backend/tests/test_schema.py` | create | 应用导入与七表迁移/约束测试 |
| `backend/tests/test_password.py`、`backend/tests/test_sessions.py`、`backend/tests/test_auth_api.py` | create | 密码、限流、会话与首登/写保护 |
| `backend/tests/test_upsert.py`、`backend/tests/test_classification.py` | create | URL 身份、字段合并、多语种明确规则 |
| `backend/tests/test_queries.py`、`backend/tests/test_articles_api.py` | create | 查询、分页、排序、筛选与 DTO |
| `backend/tests/test_bookmarks.py`、`backend/tests/test_bookmarks_api.py` | create | 收藏持久化和 API |
| `backend/tests/test_sources.py`、`backend/tests/test_safe_http.py` | create | 逐入口许可与 SSRF/请求边界 |
| `backend/tests/test_parsers.py`、`backend/tests/test_ingest.py` | create | 内存夹具、内容排除、采集事务 |
| `backend/tests/test_jobs.py`、`backend/tests/test_jobs_api.py` | create | 入队/重试并发和任务 JSON |
| `backend/tests/test_worker.py`、`backend/tests/test_schedule.py` | create | 串行消费、中断、07:30 与当天一次补跑 |
| `backend/tests/test_recovery_integration.py`、`backend/tests/test_backup.py` | create | 两连接重启、读写隔离、备份恢复 |
| `backend/tests/test_verification.py` | create | 五站逐入口证据文件与启用一致性 |
| `backend/tests/test_deployment.py`、`backend/tests/test_security_audit.py` | create | 部署静态契约、全路由负向与日志审计 |
| `backend/tests/acceptance/__init__.py`、`backend/tests/acceptance/test_live.py` | create | 授权目标环境的真实 HTTPS/来源/调度验收 |
| `backend/tests/acceptance/test_release.py` | create | 汇总真实证据和发布门禁，不虚构通过 |
| `backend/verification/prtimes.json`、`backend/verification/happi.json` | create | 当前运行环境下的逐入口使用条件与 probe 证据 |
| `backend/verification/qingyan.json`、`backend/verification/pbn.json`、`backend/verification/cosin.json` | create | 其余三站独立许可/入口结论 |
| `backend/verification/live-source.json`、`backend/verification/live-schedule.json` | create | 真来源与真实 07:30/恢复演练结果 |
| `backend/verification/live-restore.json`、`backend/verification/live-audit.json`、`backend/verification/release.json` | create | 恢复、安全审计和发布结论 |
| `backend/Dockerfile`、`backend/.dockerignore` | create | 单一应用镜像，API 与 worker 复用 |
| `deploy/compose.yaml`、`deploy/Caddyfile`、`deploy/env.example` | create | 三服务、私密挂载、HTTPS 和无公网数据库端口 |
| `deploy/README.md` | create | 迁移、发布、回滚、停写恢复、验收与错误查看命令 |

测试共用 fixture 的创建随 owner 推进：001 提供 `now`、`settings`、`client`；002 提供 `db`、`entry_factory`；003 提供 `article_factory`；004 提供 `job_factory`；008 提供 `user_client`；018 提供 `http_lab`；026 提供 `worker_lab`；033 提供 `verification_files`；041 提供 `live_env`。fixture 不读取真实来源或真实凭据，除显式 `--live` 验收。每个 fixture 的具体契约由接口账本唯一声明。
