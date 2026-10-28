## 条目、查找与收藏任务

- [x] **Task backend-009: 按完整链接幂等更新并保留可靠元信息**

**Files:**
- Create: `backend/app/articles.py`、`backend/tests/test_upsert.py`

**Reasoning:**
- D-010、D-027 要求精确链接身份，缺失元信息不擦除旧值；收藏始终引用同一ID。

**Depends on:** backend-005

**Interfaces:**
- Consumes: I03 Article/Bookmark。
- Produces: I09 Headline、WriteResult、dedup_url、upsert_headline。
- Contract checks: 仅去空格和片段；参数/大小写/媒体不同不合并；标题与元信息校验边界；首次来源不变。

**Step 1: Write the failing test**
```python
from dataclasses import replace
from app.articles import Headline, dedup_url, upsert_headline

def test_identity_and_reliable_merge(db, entry_factory, now):
    e = entry_factory()
    h = Headline(e.source_id, e.id, ' https://example.org/a?x=1#top ', '旧标题')
    a = upsert_headline(db, h, now)
    b = upsert_headline(db, replace(h, title='新标题',
                        original_url='https://example.org/a?x=1#other'), now)
    db.commit()
    assert a.article_id == b.article_id and b.updated
    assert dedup_url('https://x/a?b=1&a=2#x') == 'https://x/a?b=1&a=2'
    assert dedup_url('https://x/a?b=1&a=2') != dedup_url('https://x/a?a=2&b=1')
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_upsert.py::test_identity_and_reliable_merge -q`
- Expected: upsert/Headline 尚未定义。

**Step 3: Write minimal implementation**
```python
def dedup_url(url):
    """按用户确认的精确规则比较，不改写查询参数或路径。"""
    return url.strip().split('#', 1)[0]

def upsert_headline(db, h, now):
    """写入允许元信息；调用方控制事务，唯一键解决同链接并发。"""
    key = dedup_url(h.original_url)
    existing = db.scalar(select(Article).where(Article.dedup_url == key))
    if existing is None:
        # SQLite INSERT ON CONFLICT DO NOTHING 后重读，避免并发重复。
        db.execute(sqlite_insert(Article).values(
            source_id=h.source_id, first_entry_id=h.first_entry_id,
            original_url=h.original_url.strip(), dedup_url=key, title=h.title,
            search_text=unicodedata.normalize('NFKC', h.title).casefold(),
            category_codes=list(h.category_codes), updated_at=now
        ).on_conflict_do_nothing(index_elements=['dedup_url']))
```
- 补全所有可得字段的首次写入与冲突后重读/合并；返回added/updated按实际变化而不是请求次数。search_text最终拼接标题和Source.name再NFKC/casefold。只用非空可靠字段更新；空分类/未知日期不抹旧值；不更改首次来源归属。article URL只允许安全http(s)、无凭据且长度合规，不发请求。并发测试用独立Session，测保留日期/图片/收藏。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_upsert.py -q`
- Expected: PASS。自审唯一约束与更新计数、事务解释一致，不把同事件不同链接视为重复。

**Step 5: Commit**
```bash
git add backend/app/articles.py backend/tests/test_upsert.py
git commit -m "feat: upsert headlines by exact original link"
```

- [x] **Task backend-010: 用栏目和多语明确词语生成受控分类**

**Files:**
- Create: `backend/app/classification.py`、`backend/config/classification.json`、`backend/tests/test_classification.py`

**Reasoning:**
- D-011 的分类必须可追溯，未命中时保持未知，不能从媒体国别推断市场。

**Depends on:** backend-009

**Interfaces:**
- Consumes: I09 Headline 的标题/栏目；七CategoryCode。
- Produces: I10 Rule/Classification/load_rules/classify。
- Contract checks: 多分类、固定顺序去重、未知空数组；地区/品类只有明确语词规则才赋值。

**Step 1: Write the failing test**
```python
from app.classification import classify, load_rules

def test_explicit_multilingual_rules():
    rules = load_rules('config/classification.json')
    assert 'new_ingredients' in classify('New ingredient announced', None, rules).category_codes
    assert 'regulation_compliance' in classify('化粧品規制の更新', None, rules).category_codes
    assert 'new_products' in classify('신제품 출시', None, rules).category_codes
    unknown = classify('Company update', None, rules)
    assert (unknown.category_codes, unknown.region, unknown.product_type) == ((), None, None)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_classification.py::test_explicit_multilingual_rules -q`
- Expected: 规则加载/分类器不存在。

**Step 3: Write minimal implementation**
```python
def classify(title, section, rules):
    """只用明示栏目或标题词语；无证据就保留未知值。"""
    text = unicodedata.normalize('NFKC', f'{section or ""}\n{title}').casefold()
    categories, regions, products = set(), set(), set()
    for rule in rules:
        if re.search(rule.pattern, text):
            if rule.field == 'category':
                categories.add(rule.value)
            elif rule.field == 'region':
                regions.add(rule.value)
            elif rule.field == 'product_type':
                products.add(rule.value)
    return Classification(tuple(c for c in CATEGORY_CODES if c in categories),
        next(iter(regions)) if len(regions) == 1 else None,
        next(iter(products)) if len(products) == 1 else None)
```
- 配置逐条包含pattern/value/evidence。七类使用明确新品/趋势/新原料/研发技术/包装剂型/OEM-ODM/法规词，提供中英日韩样本与反例。地区规则只识别明确“在日本上市”等市场词组，不用标题中的媒体名或公司国籍；冲突结果保留NULL，使用集合聚合防止后续命中覆写冲突。不增加模型或语义推断。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_classification.py -q`
- Expected: PASS；七类都有正例，模糊标题/冲突/媒体国别均负向通过。自审规则旁说明证据，不承诺完整分类覆盖。

**Step 5: Commit**
```bash
git add backend/app/classification.py backend/config/classification.json backend/tests/test_classification.py
git commit -m "feat: classify explicit title and section evidence"
```

- [x] **Task backend-011: 实现包含收藏状态的组合查询与页码排序**

**Files:**
- Extend planned: `backend/app/articles.py`
- Create: `backend/tests/test_queries.py`

**Reasoning:**
- D-024、D-036、D-037 要求服务端过滤/分页和每条bookmarked；分页不伪称跨更新快照。

**Depends on:** backend-010

**Interfaces:**
- Consumes: I03 Article/Bookmark、I10 分类值。
- Produces: I11 ArticleQuery/ArticleOut/ArticlePage/FiltersOut 和四个查询函数。
- Contract checks: json_each多分类、NULL未知筛选、字面搜索、日期含边界、总数与页面一致。

**Step 1: Write the failing test**
```python
from datetime import date
from app.articles import ArticleQuery, list_articles

def test_filters_order_and_page_movement(db, article_factory):
    unknown = article_factory(reported_date=None)
    old = article_factory(reported_date=date(2026, 1, 1))
    latest = article_factory(reported_date=date(2026, 2, 1))
    first = list_articles(db, ArticleQuery(page=1, page_size=1))
    assert [i.id for i in first.items] == [latest.id]
    article_factory(reported_date=date(2026, 3, 1))
    second = list_articles(db, ArticleQuery(page=2, page_size=1))
    assert second.items[0].id == latest.id  # 明确接受后台插入后的跨页位移。
    assert list_articles(db, ArticleQuery()).items[-1].id == unknown.id
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_queries.py::test_filters_order_and_page_movement -q`
- Expected: I11 查询契约未实现。

**Step 3: Write minimal implementation**
```python
def list_articles(db, query, bookmarked_only=False):
    """同一筛选计算总数与当前页；不承诺跨请求快照。"""
    marked = exists(select(Bookmark.article_id).where(Bookmark.article_id == Article.id))
    statement = select(Article, marked.label('bookmarked'))
    if bookmarked_only:
        statement = statement.join(Bookmark, Bookmark.article_id == Article.id)
        statement = statement.order_by(Bookmark.created_at.desc(), Article.id.desc())
    else:
        statement = statement.order_by(Article.reported_date.desc(), Article.id.desc())
```
- 在同一读取事务应用全部过滤，再count和limit/offset；分类使用参数化json_each exists，搜索escape LIKE通配符，地区/品类未知谓词IS NULL。article_out使用同一exists规则；filters返回七分类及数据库实际非空地区/品类，未知值独立字段。parse_query拒绝重复/非法值与过大页容量，报400。补测数据不变页序、组合过滤、q中的%/_与每条bool。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_queries.py -q`
- Expected: PASS。自审索引和NULL顺序，不追加全文服务或快照。

**Step 5: Commit**
```bash
git add backend/app/articles.py backend/tests/test_queries.py
git commit -m "feat: query headlines with deterministic page ordering"
```

- [x] **Task backend-012: 注册标题列表、详情与筛选选项 HTTP 契约**

**Files:**
- Create: `backend/app/api_articles.py`、`backend/tests/test_articles_api.py`
- Extend planned: `backend/app/main.py`、`backend/tests/conftest.py`（请求级独立 Session fixture）

**Reasoning:**
- D-024 的只读接口与业务查询分开review，保证前端消费者取得同一条目身份与NULL含义。

**Depends on:** backend-008, backend-011

**Interfaces:**
- Consumes: I08 require_session、I11 查询/DTO。
- Produces: I12 articles_router 与三个命名路由。
- Contract checks: 200字段精确、缺失404、非法筛选400、无会话401；无正文/摘要字段。

**Step 1: Write the failing test**
```python
def test_article_contract_and_filters(user_client, article_factory):
    a = article_factory(reported_date=None, category_codes=[])
    r = user_client.get('/api/articles')
    assert r.status_code == 200
    assert r.json()['items'][0]['bookmarked'] is False
    item = user_client.get(f'/api/articles/{a.id}').json()
    assert item['reported_date'] is None and item['category_codes'] == []
    assert {'body', 'summary', 'event_id'}.isdisjoint(item)
    assert user_client.get('/api/articles?page_size=101').status_code == 400
    assert len(user_client.get('/api/filters').json()['categories']) == 7
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_articles_api.py::test_article_contract_and_filters -q`
- Expected: 阅读路由404。

**Step 3: Write minimal implementation**
```python
articles_router = APIRouter(dependencies=[Depends(require_session)])

@articles_router.get('/api/articles', name='article_list')
def article_list(request: Request, db=Depends(get_db)):
    """只返回允许元信息和服务端收藏标记。"""
    return list_articles(db, parse_query(request.query_params))

@articles_router.get('/api/articles/{id}', name='article_detail')
def article_detail(id: int, db=Depends(get_db)):
    article = db.get(Article, id)
    if article is None:
        raise ApiError('article_not_found', '资讯不存在', 404)
    return article_out(db, article)
```
- 增加filters route并在工厂include_router；正整数/类型错误统一400。响应模型显式列白名单字段，禁止自动序列化ORM内部列或原始数据。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_articles_api.py tests/test_queries.py -q`
- Expected: PASS；补测无会话、日期倒置、未知category和重复参数。自审schema字段与唯一账本一致。

**Step 5: Commit**
```bash
git add backend/app/api_articles.py backend/app/main.py backend/tests/test_articles_api.py
git commit -m "feat: expose authenticated headline discovery api"
```

- [x] **Task backend-013: 持久收藏引用并使用收藏时间排序**

**Files:**
- Create: `backend/app/bookmarks.py`、`backend/tests/test_bookmarks.py`

**Reasoning:**
- D-031 明确首页与收藏排序不同；重复收藏不改变时间，取消不删除资讯。

**Depends on:** backend-011

**Interfaces:**
- Consumes: I03、I11。
- Produces: I13 set_bookmark/list_bookmarks、BookmarkOut。
- Contract checks: 幂等操作、同链接更新与重新连接后仍引用原ID；收藏列表bool恒true。

**Step 1: Write the failing test**
```python
from datetime import date, timedelta
from app.bookmarks import set_bookmark, list_bookmarks
from app.articles import ArticleQuery

def test_persistent_reference_and_order(db, article_factory, now):
    a = article_factory(reported_date=date(2026, 2, 1))
    b = article_factory(reported_date=date(2026, 1, 1))
    set_bookmark(db, a.id, True, now)
    set_bookmark(db, b.id, True, now + timedelta(seconds=1))
    set_bookmark(db, a.id, True, now + timedelta(seconds=2))
    page = list_bookmarks(db, ArticleQuery())
    assert [i.id for i in page.items] == [b.id, a.id]
    assert all(i.bookmarked for i in page.items)
    set_bookmark(db, a.id, False, now)
    assert db.get(type(a), a.id) is not None
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_bookmarks.py::test_persistent_reference_and_order -q`
- Expected: 收藏service未实现。

**Step 3: Write minimal implementation**
```python
def set_bookmark(db, article_id, value, now):
    """幂等改变引用，重复收藏不能重置最初收藏时间。"""
    if db.get(Article, article_id) is None:
        raise ApiError('article_not_found', '资讯不存在', 404)
    if value:
        db.execute(sqlite_insert(Bookmark).values(article_id=article_id, created_at=now)
                   .on_conflict_do_nothing(index_elements=['article_id']))
    else:
        db.execute(delete(Bookmark).where(Bookmark.article_id == article_id))
    db.commit()
    return BookmarkOut(article_id=article_id, bookmarked=value)
```
- list_bookmarks直接调用list_articles(...,bookmarked_only=True)。补测同时间article_id倒序、关闭连接重开、同URL upsert后标题跟随更新和不存在404。事务失败必须rollback后抛出，不返回成功DTO。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_bookmarks.py tests/test_upsert.py -q`
- Expected: PASS。自审书签未复制标题/元信息，首页排序未改。

**Step 5: Commit**
```bash
git add backend/app/bookmarks.py backend/tests/test_bookmarks.py
git commit -m "feat: persist idempotent bookmarks by creation time"
```

- [x] **Task backend-014: 提供收藏 API 并验证多入口状态及写失败**

**Files:**
- Create: `backend/app/api_bookmarks.py`、`backend/tests/test_bookmarks_api.py`
- Extend planned: `backend/app/main.py`

**Reasoning:**
- D-036 要求首页、详情、收藏和写结果一致，保存失败不能伪报成功。

**Depends on:** backend-012, backend-013

**Interfaces:**
- Consumes: I08 require_session/require_write、I13。
- Produces: I14 bookmarks_router 与GET/PUT/DELETE。
- Contract checks: 写返回article_id/bookmarked；缺CSRF403、无会话401、非法筛选400；存储失败503且保留原状态。

**Step 1: Write the failing test**
```python
def test_state_consistency_and_write_failure(user_client, article_factory, monkeypatch):
    a = article_factory()
    r = user_client.put(f'/api/bookmarks/{a.id}', json={})
    assert r.json() == {'article_id': a.id, 'bookmarked': True}
    assert user_client.get(f'/api/articles/{a.id}').json()['bookmarked'] is True
    assert user_client.get('/api/articles').json()['items'][0]['bookmarked'] is True
    assert user_client.get('/api/bookmarks').json()['items'][0]['bookmarked'] is True
    from app import api_bookmarks
    def storage_failure(*args, **kwargs):
        from app.errors import ApiError
        raise ApiError('storage_unavailable', '存储暂不可用', 503)
    monkeypatch.setattr(api_bookmarks, 'set_bookmark', storage_failure)
    assert user_client.delete(f'/api/bookmarks/{a.id}').status_code == 503
    assert user_client.get(f'/api/articles/{a.id}').json()['bookmarked'] is True
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_bookmarks_api.py::test_state_consistency_and_write_failure -q`
- Expected: 收藏写路由404。

**Step 3: Write minimal implementation**
```python
@bookmarks_router.put('/api/bookmarks/{article_id}', name='bookmark_put',
                      dependencies=[Depends(require_write)])
def bookmark_put(article_id: int, db=Depends(get_db)):
    """提交成功才确认收藏；数据库错误由统一边界脱敏。"""
    return set_bookmark(db, article_id, True, datetime.now(UTC))
```
- GET使用require_session和ArticleQuery；DELETE使用require_write并返回false。全局SQLAlchemy错误处理rollback/503；另用真实SQLite只读连接或注入commit异常验证数据库事务未部分写入，不能只用mock覆盖回滚。空body的DELETE仍验证Origin/CSRF。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_bookmarks_api.py tests/test_bookmarks.py -q`
- Expected: PASS。自审三入口bool与写确认完全同义，不增加历史快照。

**Step 5: Commit**
```bash
git add backend/app/api_bookmarks.py backend/app/main.py backend/tests/test_bookmarks_api.py
git commit -m "feat: expose consistent bookmark state and failures"
```
