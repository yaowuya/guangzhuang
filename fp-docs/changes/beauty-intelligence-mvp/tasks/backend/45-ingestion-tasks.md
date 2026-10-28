## 白名单元信息解析与写入任务

- [x] **Task backend-019: 解析 RSS 元信息并彻底忽略内文模块**

**Files:**
- Create: `backend/app/parsers.py`、`backend/tests/test_parsers.py`

**Reasoning:**
- D-008、D-009、D-012 接受RSS响应经过内存，但不能因此提取、存储或记录description/content。

**Depends on:** backend-010, backend-018

**Interfaces:**
- Consumes: I09 Headline、I15 EntrySpec、I18 Fetched。
- Produces: I19 ParseBatch/ParseError/parse_rss。
- Contract checks: RSS2/RDF元信息、未知日期NULL、缺关键字段跳过；DTD/实体拒绝，不执行脚本。

**Step 1: Write the failing test**
```python
from app.parsers import parse_rss

def test_rss_metadata_only(entry_factory):
    e = entry_factory(kind='rss')
    raw = b'''<rss><channel><item><title>Valid title</title>
      <link>https://example.org/a</link><description>CONTENT_SENTINEL</description>
      </item><item><title>Missing link</title></item></channel></rss>'''
    batch = parse_rss(raw, e)
    assert len(batch.headlines) == 1
    assert batch.headlines[0].reported_date is None
    assert batch.skipped['missing_url'] == 1
    assert 'CONTENT_SENTINEL' not in repr(batch)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_parsers.py::test_rss_metadata_only -q`
- Expected: RSS解析器不存在。

**Step 3: Write minimal implementation**
```python
def parse_rss(raw, entry):
    """仅读标题、链接、日期、栏目和允许图片元信息，不读取内文元素。"""
    root = defusedxml.ElementTree.fromstring(raw, forbid_dtd=True,
                                           forbid_entities=True, forbid_external=True)
    rows = root.findall('./channel/item') + root.findall('{http://purl.org/rss/1.0/}item')
    headlines, skipped = [], Counter()
    for row in rows:
        title = (row.findtext('title') or row.findtext('{http://purl.org/rss/1.0/}title') or '').strip()
        link = (row.findtext('link') or row.findtext('{http://purl.org/rss/1.0/}link') or '').strip()
        if not title or not link:
            skipped['missing_title' if not title else 'missing_url'] += 1
            continue
        headlines.append(Headline(entry.source_id, entry.id, link, title))
    return ParseBatch(headlines, dict(skipped))
```
- 补全RFC822/pubDate、DC date和RDF namespace日期；只保留来源明确的当地报道日期，日期无效为NULL并计理由。图片只读明确media thumbnail/enclosure URL，不从description或正文HTML搜图；后续I21再审许可。未识别RSS结构/畸形XML抛ParseError，合法空channel成功零条；不把解析错误吞成空列表。夹具内文仅用哨兵短语，不复制真实正文。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_parsers.py -q`
- Expected: PASS；覆盖RSS2/RDF、DTD、恶意链接和日期。自审无description/content/summary提取或原始响应日志。

**Step 5: Commit**
```bash
git add backend/app/parsers.py backend/tests/test_parsers.py
git commit -m "feat: parse rss headline metadata only"
```

- [x] **Task backend-020: 从已核验公开列表选择元信息且不补取文章详情**

**Files:**
- Extend planned: `backend/app/parsers.py`、`backend/tests/test_parsers.py`

**Reasoning:**
- D-012 只允许可用且许可明确的公开列表补充，选择器必须有逐入口运行证据。

**Depends on:** backend-019

**Interfaces:**
- Consumes: I15 EntrySpec、I19 ParseBatch/ParseError。
- Produces: I20 ListSelection/parse_list。
- Contract checks: selector空值不得运行；只选列表指定元信息，HTML脚本与正文节点不处理。

**Step 1: Write the failing test**
```python
from app.parsers import parse_list, ListSelection

def test_public_list_has_no_detail_fetch(entry_factory):
    e = entry_factory(kind='public_list')
    e.selection = ListSelection(container='ul', item='li.news', title='a.title', link='a.title')
    raw = b'<ul><li class="news"><a class="title" href="/a">A title</a></li></ul><script>bad()</script>'
    batch = parse_list(raw, e)
    assert [h.title for h in batch.headlines] == ['A title']
    assert batch.headlines[0].original_url.endswith('/a')
    assert not hasattr(batch.headlines[0], 'body')
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_parsers.py::test_public_list_has_no_detail_fetch -q`
- Expected: ListSelection/parse_list尚不存在。

**Step 3: Write minimal implementation**
```python
def parse_list(raw, entry):
    """仅消费入口核验的CSS选择器，不请求链接页面。"""
    if entry.selection is None:
        raise ParseError('入口列表结构尚未核验')
    soup = BeautifulSoup(raw, 'html.parser')
    for node in soup(['script', 'style']):
        node.decompose()
    headlines, skipped = [], Counter()
    for item in soup.select(entry.selection.item):
        title_node = item.select_one(entry.selection.title)
        link_node = item.select_one(entry.selection.link)
        if title_node is None or link_node is None or not link_node.get('href'):
            skipped['missing_title' if title_node is None else 'missing_url'] += 1
            continue
        headlines.append(Headline(entry.source_id, entry.id,
                         urljoin(entry.url, link_node['href']), title_node.get_text(' ', strip=True)))
    return ParseBatch(headlines, dict(skipped))
```
- date/section/image/credit只从核验选定属性/节点提取，不遍历文章正文，不执行脚本。零条需已验证结构存在的空列表标记才能当合法空响应；选择器失配/页面结构变更要ParseError。ListSelection的container必填，用于验证列表结构；empty可空，存在时作为明确零条标记；字段已固定在账本中。测试夹具明确设置container。不得猜写实际站点CSS；五站任务从未来真实核验生成配置。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_parsers.py -q`
- Expected: PASS；补测恶意href、缺关键项、空容器与错结构。自审不引入文章详情抓取和通用爬虫。

**Step 5: Commit**
```bash
git add backend/app/parsers.py backend/tests/test_parsers.py
git commit -m "feat: parse approved public listing metadata"
```

- [x] **Task backend-021: 限制图片字段为获许可的安全外链**

**Files:**
- Create: `backend/app/ingest.py`、`backend/tests/test_ingest.py`

**Reasoning:**
- P-010、D-009 要求图片许可独立核验，缺图不影响标题和收藏，不允许失败后代理。

**Depends on:** backend-020

**Interfaces:**
- Consumes: I15 EntrySpec.image_allowed/image_hosts。
- Produces: I21 allowed_image。
- Contract checks: 未许可返回两个NULL；只准HTTPS无凭据的明确主机，拒绝data/file/private字面IP；无网络副作用。

**Step 1: Write the failing test**
```python
from app.ingest import allowed_image

def test_images_are_links_with_permission(entry_factory, monkeypatch):
    e = entry_factory()
    e.image_allowed, e.image_hosts = False, {'images.example.org'}
    assert allowed_image('https://images.example.org/a.jpg', 'Source', e) == (None, None)
    e.image_allowed = True
    assert allowed_image('https://images.example.org/a.jpg', 'Source', e) == (
        'https://images.example.org/a.jpg', 'Source')
    assert allowed_image('data:image/png;base64,AAAA', None, e) == (None, None)
    assert allowed_image('https://127.0.0.1/a.jpg', None, e) == (None, None)
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_ingest.py::test_images_are_links_with_permission -q`
- Expected: 图片许可过滤尚未定义。

**Step 3: Write minimal implementation**
```python
def allowed_image(url, credit, entry):
    """只返回可供浏览器直连的允许外链；不下载或探测图片。"""
    if not entry.image_allowed or not url:
        return None, None
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.hostname not in entry.image_hosts or len(url) > 4096):
        return None, None
    return url, credit if credit and len(credit) <= 500 else None
```
- 严格URL控制字符/端口/IDNA/字面IP检查复用URL边界，不调用SafeClient.fetch图片。测试patch socket/HTTP调用为立即失败，证明过滤本身无出站。API无图片代理路径；未来浏览器失败仅降级由前端负责。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_ingest.py::test_images_are_links_with_permission -q`
- Expected: PASS。自审数据库/DTO只含URL/署名，图片许可false不是入口标题许可false。

**Step 5: Commit**
```bash
git add backend/app/ingest.py backend/tests/test_ingest.py
git commit -m "feat: retain only permitted source image links"
```

- [x] **Task backend-022: 在单入口事务中采集、分类并提交结果**

**Files:**
- Extend planned: `backend/app/ingest.py`、`backend/tests/test_ingest.py`、`backend/tests/conftest.py`（http_lab client factory）

**Reasoning:**
- D-008、D-023 要求成功结果可保留，解析失败/截断不伪报成功，合法零条与首次空库区分。

**Depends on:** backend-009, backend-010, backend-016, backend-018, backend-021

**Interfaces:**
- Consumes: I09/I10/I16/I18/I19/I20/I21。
- Produces: I22 IngestResult/ingest_entry/safe_error。
- Contract checks: 再校验入口、一次受控fetch、白名单值对象；条目与入口成功时间同事务提交；错误不写原始响应。

**Step 1: Write the failing test**
```python
from app.ingest import ingest_entry
from app.models import Article
from sqlalchemy import select

def test_entry_atomicity_zero_and_invalid_rows(db, entry_factory, http_lab, now):
    e = entry_factory(kind='rss', enabled=True, verification_status='allowed',
                      verification_reason='测试许可', verification_reference='https://example.org/terms')
    http_lab.reply(e.url, body=b'<rss><channel><item><title>No link</title></item></channel></rss>')
    result = ingest_entry(db, e, http_lab.client_for(e), now)
    assert result.added == result.updated == 0
    assert result.skipped['missing_url'] == 1
    assert db.scalars(select(Article)).all() == []
    assert e.last_success_at == now
```
**Step 2: Run test to verify it fails**
- Run: `cd backend && python -m pytest tests/test_ingest.py::test_entry_atomicity_zero_and_invalid_rows -q`
- Expected: 单入口采集函数尚不存在。

**Step 3: Write minimal implementation**
```python
def ingest_entry(db, entry, client, now):
    """完成一次入口事务；错误回滚，不污染最后成功元信息。"""
    if entry.id not in {e.id for e in eligible_entries(db)}:
        raise ApiError('source_not_enabled', '入口未经核验或未启用', 409)
    fetched = client.fetch(entry.url)
    batch = parse_rss(fetched.body, entry) if entry.kind == 'rss' else parse_list(fetched.body, entry)
    added = updated = 0
    for h in batch.headlines:
        c = classify(h.title, h.section, load_rules(db.info['rules_config']))
        image, credit = allowed_image(h.image_url, h.image_credit, entry)
        result = upsert_headline(db, replace(h, category_codes=c.category_codes,
            region=c.region, product_type=c.product_type, image_url=image, image_credit=credit), now)
        added += int(result.added)
        updated += int(result.updated)
    entry.last_success_at, entry.last_error = now, None
    db.commit()
    return IngestResult(added, updated, batch.skipped)
```
- db.info由get_db/worker会话设置rules_config与入口静态配置；SourceEntry运行时附加经I15校验的selection/hosts/image条件，不新增数据库列。无效关键字段计跳过；存储异常回滚整入口，safe_error仅返回受控错误码和短消息。error/state结果由worker另一短事务记录；不把RSS原始body/HTML异常摘录写入日志。

**Step 4: Run test to verify it passes**
- Run: `cd backend && python -m pytest tests/test_ingest.py tests/test_parsers.py tests/test_upsert.py -q`
- Expected: PASS；补测畸形/过大响应失败、写到一半出错原子回滚、未知字段保留旧值、无新增。自审网络操作不持有SQLite写锁。

**Step 5: Commit**
```bash
git add backend/app/ingest.py backend/tests/test_ingest.py
git commit -m "feat: ingest approved metadata in entry transactions"
```
