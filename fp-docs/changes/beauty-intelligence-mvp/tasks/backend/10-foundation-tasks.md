## 工程与七表迁移任务

- [x] **Task backend-001: 建立可导入应用与安全配置测试入口**

**Files:**
- Create: `backend/pyproject.toml`、`backend/.gitignore`、`backend/app/__init__.py`、`backend/app/main.py`、`backend/app/config.py`、`backend/app/errors.py`
- Test: `backend/tests/__init__.py`、`backend/tests/conftest.py`、`backend/tests/test_bootstrap.py`

**Reasoning:**
- P-012、D-004 的绿地起点。把脚手架、配置与首个可测试应用合在一个交付边界，不建立空分层。

**Depends on:** None

**Interfaces:**
- Consumes: I01 的 Global Constraints 配置值。
- Produces: I01、T01 的 now/settings/client；公开配置只含无密钥值。
- Contract checks: 缺私密配置拒绝启动；导入无联网/建库副作用；生成服务端 request_id，异常不回显输入。

**Step 1: Write the failing test**
```python
from fastapi.testclient import TestClient
from app.main import create_app
from app.errors import ApiError

def test_factory_and_safe_errors(settings):
    app = create_app(settings)
    @app.get('/test-error')
    def fail():
        raise ApiError('storage_unavailable', '存储暂不可用', 503)
    r = TestClient(app, base_url=settings.public_origin).get('/test-error')
    assert r.status_code == 503
    assert set(r.json()) == {'code', 'message', 'request_id'}
    assert r.json()['request_id']
```
**Step 2: Run test to verify it fails**
- Run（用户明确选择先在本机 Windows 开发）：先在仓库根运行 `"$PYTHON_EXE" -m venv backend/.venv`（`PYTHON_EXE` 为已核验的 Python 3.12 绝对路径），然后 `export PATH="$(pwd)/backend/.venv/Scripts:$PATH"`，核对 `python -c 'import sys; print(sys.executable)'` 指向 `backend/.venv/Scripts/python.exe`；再运行 `python -m pip install -e './backend[test]'`；最后 `cd backend && python -m pytest tests/test_bootstrap.py::test_factory_and_safe_errors -q`。安装及版本输出独立记录，不以安装失败当业务 RED。
- Expected: 测试依赖就绪后，首次收集因 `app.main` 尚无 create_app 失败；Windows GREEN 只适用于本任务可移植 FastAPI 启动与错误边界，Linux 锁、容器和真实部署仍须另行验证。

**Step 3: Write minimal implementation**
```python
def create_app(settings=None):
    """构造同源应用；不在导入阶段联网或迁移数据库。"""
    settings = settings or Settings.from_environment()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.now = lambda: datetime.now(UTC)
    install_errors(app)
    return app
```
- 使用显式 dataclass Settings 与文件读取；测试生成独立 Argon2id 摘要，不提交真实口令。`install_errors`注册ApiError、RequestValidationError、Starlette HTTPException与未知异常的固定脱敏包；框架404/405分别为not_found/method_not_allowed，未知500为internal_error，未知异常只记request_id与异常类型。测试同时覆盖缺配置和无网络导入。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_bootstrap.py -q`
- Expected: 在 Windows 仓库级 venv 中 PASS，并保留实际命令及版本；自审公共 docstring 与配置校验一致，不把调试堆栈暴露到响应。Linux 最终容器与真实环境验收不由此替代。

**Step 5: Commit**
```bash
git add backend/pyproject.toml backend/.gitignore backend/app/__init__.py backend/app/main.py backend/app/config.py backend/app/errors.py backend/tests/__init__.py backend/tests/conftest.py backend/tests/test_bootstrap.py
git commit -m "feat: bootstrap private headline api"
```

- [x] **Task backend-002: 建立来源与入口迁移及 SQLite 连接约束**

**Files:**
- Create: `backend/app/database.py`、`backend/app/models.py`、`backend/alembic.ini`、`backend/alembic/env.py`、`backend/alembic/versions/0001_sources.py`
- Test: `backend/tests/test_schema.py`；Extend planned: `backend/tests/conftest.py`

**Reasoning:**
- D-022、D-035 要求来源身份和入口许可分别持久保存。只迁移两个当前所需表。

**Depends on:** backend-001

**Interfaces:**
- Consumes: I01 Settings。
- Produces: I02；T01 的 db/entry_factory（临时文件库、每测回滚/销毁）。
- Contract checks: FK开启、同站入口URL唯一、pending默认禁用、allowed/restricted需原因和依据。

**Step 1: Write the failing test**
```python
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

def test_source_entry_constraints(db, entry_factory):
    e = entry_factory()
    assert (e.verification_status, e.enabled) == ('pending', False)
    assert db.scalar(text('PRAGMA foreign_keys')) == 1
    with pytest.raises(IntegrityError):
        entry_factory(source_id=e.source_id, url=e.url)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_schema.py::test_source_entry_constraints -q`
- Expected: 来源模型/表尚不存在，测试失败，不得把缺依赖误当业务 RED。

**Step 3: Write minimal implementation**
```python
class SourceEntry(Base):
    """单个候选入口；许可结论和访问故障分开存储。"""
    __tablename__ = 'source_entries'
    __table_args__ = (
        UniqueConstraint('source_id', 'url'),
        CheckConstraint("verification_status IN ('pending','allowed','restricted')"),
        CheckConstraint("NOT enabled OR (verification_status='allowed' AND "
                        "verification_reason IS NOT NULL AND verification_reference IS NOT NULL)"),
    )
```
- 完整声明设计的 Source/SourceEntry 所有字段；额外 CHECK 约束 allowed/restricted 的非空非空串原因/依据。`make_engine`在connect event开FK/busy_timeout；db_session为上下文管理器，get_db为FastAPI yield依赖，关闭/rollback并把rules_config/source_config路径放db.info。迁移env仅从环境读取数据库URL，不要求登录私密配置、不硬编码生产路径。0001 upgrade/downgrade对称。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_schema.py::test_source_entry_constraints -q`
- Expected: PASS；补测孤儿外键、无依据启用和受限入口启用失败。自审约束说明实际兜底范围，运行核验由 I16 负责。

**Step 5: Commit**
```bash
git add backend/app/database.py backend/app/models.py backend/alembic.ini backend/alembic/env.py backend/alembic/versions/0001_sources.py backend/tests/test_schema.py backend/tests/conftest.py
git commit -m "feat: persist fixed source entry permissions"
```

- [x] **Task backend-003: 建立标题与收藏引用迁移**

**Files:**
- Create: `backend/alembic/versions/0002_articles.py`
- Extend planned: `backend/app/models.py`、`backend/tests/test_schema.py`、`backend/tests/conftest.py`

**Reasoning:**
- D-010、D-022、D-031 的去重、可空元信息与收藏排序必须有物理约束，不复制收藏快照。

**Depends on:** backend-002

**Interfaces:**
- Consumes: I02 Base/Source/SourceEntry。
- Produces: I03；T01 article_factory，默认合法标题与URL、未知日期、空分类。
- Contract checks: dedup_url 二进制唯一、bookmark FK/唯一、分类合法 JSON 数组、两种排序索引。

**Step 1: Write the failing test**
```python
from sqlalchemy import inspect

def test_article_bookmark_constraints(db, article_factory):
    from app.models import Bookmark
    a = article_factory(reported_date=None, category_codes=[])
    db.add(Bookmark(article_id=a.id, created_at=a.updated_at))
    db.commit()
    assert db.get(Bookmark, a.id).article_id == a.id
    indexes = inspect(db.bind).get_indexes('articles')
    assert any(i['column_names'] == ['reported_date', 'id'] for i in indexes)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_schema.py::test_article_bookmark_constraints -q`
- Expected: Article/Bookmark 尚未映射或表缺失。

**Step 3: Write minimal implementation**
```python
class Bookmark(Base):
    """只保存资讯引用；收藏时间不跟随资讯更新。"""
    __tablename__ = 'bookmarks'
    article_id = mapped_column(ForeignKey('articles.id'), primary_key=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index('ix_bookmark_created', created_at.desc(), article_id.desc()),)
```
- Article 完整字段来自设计。CHECK 空标题/URL、json_valid、json_type='array'；受控分类在写边界校验。dedup_url 用 BINARY 唯一索引；首页日期/id倒序索引。无body、summary、image_bytes、event字段。0002 逆序删除关联表。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_schema.py -q`
- Expected: 已有迁移测试 PASS；新增重复URL、孤儿收藏、分类非法JSON的负向用例。自审可空字段注释不混淆未知与缺省。

**Step 5: Commit**
```bash
git add backend/app/models.py backend/alembic/versions/0002_articles.py backend/tests/test_schema.py backend/tests/conftest.py
git commit -m "feat: add url articles and bookmark relations"
```

- [x] **Task backend-004: 建立任务与入口结果的并发兜底迁移**

**Files:**
- Create: `backend/alembic/versions/0003_jobs.py`
- Extend planned: `backend/app/models.py`、`backend/tests/test_schema.py`、`backend/tests/conftest.py`

**Reasoning:**
- D-016、D-030、D-034 的一次活动与每日一次补跑必须跨进程重启仍成立。

**Depends on:** backend-003

**Interfaces:**
- Consumes: I02，I03。
- Produces: I04；T01 job_factory，按显式 entry_ids 建唯一结果。
- Contract checks: active_key恒1、active唯一、schedule/catchup日期非空且分别每日唯一；终态interrupted有finished_at。

**Step 1: Write the failing test**
```python
import pytest
from sqlalchemy.exc import IntegrityError

def test_job_partial_indexes(db, job_factory):
    first = job_factory(trigger='refresh', state='pending')
    with pytest.raises(IntegrityError):
        job_factory(trigger='refresh', state='pending')
    db.rollback()
    assert db.get(type(first), first.id).state == 'pending'
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_schema.py::test_job_partial_indexes -q`
- Expected: 任务表/活动约束缺失。

**Step 3: Write minimal implementation**
```python
Index('uq_active_job', UpdateJob.active_key, unique=True,
      sqlite_where=text("state IN ('pending','running')"))
Index('uq_daily_catchup', UpdateJob.schedule_date, unique=True,
      sqlite_where=text("trigger='catchup'"))
Index('uq_daily_schedule', UpdateJob.schedule_date, unique=True,
      sqlite_where=text("trigger='schedule'"))
```
- 完整映射 Job/EntryResult 字段、状态/触发 CHECK、计数非负、组合唯一与 FK。测试两个独立 Session 并发插入，另测终态不占活动键、catchup反复创建失败和日期/结束时间 CHECK；job_factory 每次提交后再启动下一次操作。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_schema.py -q`
- Expected: PASS。自审索引 predicate 与服务候选相同，不能只依靠先查后插。

**Step 5: Commit**
```bash
git add backend/app/models.py backend/alembic/versions/0003_jobs.py backend/tests/test_schema.py backend/tests/conftest.py
git commit -m "feat: constrain persistent update job concurrency"
```

- [x] **Task backend-005: 完成会话表与全迁移往返验证**

**Files:**
- Create: `backend/alembic/versions/0004_sessions.py`
- Extend planned: `backend/app/models.py`、`backend/tests/test_schema.py`

**Reasoning:**
- D-017、D-022 要求七表完整落地，并证明空库迁移与回滚不是模型声明层的假通过。

**Depends on:** backend-004

**Interfaces:**
- Consumes: I02–I04。
- Produces: I05 Session 与完整迁移链。
- Contract checks: 摘要唯一、过期索引；空临时库 Alembic head→base→head；SQLite JSON1 可用。

**Step 1: Write the failing test**
```python
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

def test_full_upgrade_downgrade(tmp_path, monkeypatch):
    url = f'sqlite:///{tmp_path / "fresh.db"}'
    monkeypatch.setenv('DATABASE_URL', url)
    cfg = Config('alembic.ini')
    command.upgrade(cfg, 'head')
    names = set(inspect(create_engine(url)).get_table_names()) - {'alembic_version'}
    assert names == {'sources','source_entries','articles','bookmarks',
                     'update_jobs','entry_results','sessions'}
    command.downgrade(cfg, 'base')
    command.upgrade(cfg, 'head')
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_schema.py::test_full_upgrade_downgrade -q`
- Expected: sessions 不在迁移结果中。

**Step 3: Write minimal implementation**
```python
class Session(Base):
    """服务器会话只存摘要，退出删除记录即撤销。"""
    __tablename__ = 'sessions'
    id = mapped_column(Integer, primary_key=True)
    token_digest = mapped_column(Text, nullable=False, unique=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False, index=True)
```
- 0004 跟随0003，使用UTC规范化读写，迁移不读取生产密码配置、不导入原型数据。SQLAlchemy SQLite 的无时区返回值在数据库边界明确转换UTC，不做本地时间推断。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_schema.py -q`
- Expected: PASS；补测摘要重复和schema中无正文/图片字节列。自审 downgrade 只用于空测试库，生产回滚须按备份确认流程。

**Step 5: Commit**
```bash
git add backend/app/models.py backend/alembic/versions/0004_sessions.py backend/tests/test_schema.py
git commit -m "feat: finish seven table alembic schema"
```
