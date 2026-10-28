import { it, expect, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { createApi, ApiError } from '../../src/api/client'
import { createSession } from '../../src/state/session'
import { useHeadlines } from '../../src/state/headlines'
import { articleFixture, authFixture, filtersFixture } from './fixtures'
import type { ArticlePage, ArticleQuery } from '../../src/api/contracts'

/** UNIT_ONLY：隔离外部 fetch，真实服务与浏览器分页归后续 UI 案例验证。 */
it('keeps confirmed data when a same-query reload fails', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  const read = vi.spyOn(api, 'listArticles').mockResolvedValue({
    items: [articleFixture()], total: 1, page: 1, page_size: 20,
  })
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref({ page: 1, page_size: 20 }), bookmarkedOnly: false }))!
  await state.load()
  read.mockRejectedValueOnce(new Error('unit offline'))
  await state.reload()
  expect(state.page.value?.items).toHaveLength(1)
  expect(state.error.value).toBeTruthy()
  scope.stop()
})

it('does not fetch before load and drops an older result when the query changes', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  let finishOld!: (result: ArticlePage) => void
  const read = vi.spyOn(api, 'listArticles')
    .mockReturnValueOnce(new Promise((resolve) => { finishOld = resolve }))
    .mockResolvedValueOnce({ items: [articleFixture({ id: 22, title: '新查询条目' })],
      total: 1, page: 1, page_size: 20 })
  const session = createSession(api)
  await session.login('unit-only')
  const query = ref<ArticleQuery>({ page: 1, page_size: 20 })
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session, query, bookmarkedOnly: false }))!
  expect(read).not.toHaveBeenCalled()
  const old = state.load()
  query.value = { q: '新查询', page: 1, page_size: 20 }
  const current = state.load()
  await current
  finishOld({ items: [articleFixture()], total: 1, page: 1, page_size: 20 })
  await old
  expect(read.mock.calls[0]?.[1]?.aborted).toBe(true)
  expect(state.page.value?.items[0]?.id).toBe(22)
  expect(state.error.value).toBeNull()
  scope.stop()
})

it('does not manufacture empty filter options when fetching options fails', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockRejectedValue(new Error('unit filter outage'))
  vi.spyOn(api, 'listArticles').mockResolvedValue({ items: [articleFixture()],
    total: 1, page: 1, page_size: 20 })
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref<ArticleQuery>({}), bookmarkedOnly: false }))!
  await state.load()
  expect(state.page.value?.total).toBe(1)
  expect(state.filters.value).toBeNull()
  expect(state.error.value).toBeTruthy()
  scope.stop()
})

it('uses the server bookmark endpoint and only applies confirmed bookmark states', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  const bookmarks = vi.spyOn(api, 'listBookmarks').mockResolvedValue({
    items: [articleFixture({ bookmarked: true })], total: 1, page: 1, page_size: 20,
  })
  const articles = vi.spyOn(api, 'listArticles')
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref<ArticleQuery>({}), bookmarkedOnly: true }))!
  await state.load()
  expect(bookmarks).toHaveBeenCalledTimes(1)
  expect(articles).not.toHaveBeenCalled()
  state.applyBookmark(7, false)
  expect(state.page.value?.items[0]?.bookmarked).toBe(false)
  scope.stop()
})

it('reports an initial read failure as a failure rather than an empty feed', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  vi.spyOn(api, 'listArticles').mockRejectedValue(
    new ApiError(401, 'unauthenticated', '会话已失效', 'unit-7'))
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref<ArticleQuery>({}), bookmarkedOnly: false }))!
  await state.load()
  expect(state.page.value).toBeNull()
  expect(state.error.value).toBe('会话已失效')
  expect(session.status.value).toBe('expired')
  scope.stop()
})

it('does not keep an authenticated page visible after the server revokes the session', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  const read = vi.spyOn(api, 'listArticles').mockResolvedValue({ items: [articleFixture()],
    total: 1, page: 1, page_size: 20 })
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref<ArticleQuery>({}), bookmarkedOnly: false }))!
  await state.load()
  read.mockRejectedValueOnce(new ApiError(401, 'unauthenticated', '已过期', 'unit-8'))
  await state.reload()
  expect(session.status.value).toBe('expired')
  expect(state.page.value).toBeNull()
  expect(state.filters.value).toBeNull()
  scope.stop()
})

it('aborts an in-flight read when its owning component scope is disposed', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  let finish!: (page: ArticlePage) => void
  const read = vi.spyOn(api, 'listArticles').mockReturnValue(new Promise((resolve) => { finish = resolve }))
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref<ArticleQuery>({}), bookmarkedOnly: false }))!
  const loading = state.load()
  scope.stop()
  expect(read.mock.calls[0]?.[1]?.aborted).toBe(true)
  finish({ items: [articleFixture()], total: 1, page: 1, page_size: 20 })
  await loading
  expect(state.page.value).toBeNull()
})

it('shows a same-filter refresh without hiding the last confirmed page', async () => {
  const api = createApi(vi.fn<typeof fetch>())
  vi.spyOn(api, 'login').mockResolvedValue(authFixture())
  vi.spyOn(api, 'getFilters').mockResolvedValue(filtersFixture())
  let finish!: (page: ArticlePage) => void
  vi.spyOn(api, 'listArticles')
    .mockResolvedValueOnce({ items: [articleFixture()], total: 1, page: 1, page_size: 20 })
    .mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
  const session = createSession(api)
  await session.login('unit-only')
  const scope = effectScope()
  const state = scope.run(() => useHeadlines({ api, session,
    query: ref<ArticleQuery>({}), bookmarkedOnly: false }))!
  await state.load()
  const pending = state.reload()
  expect(state.refreshing.value).toBe(true)
  expect(state.loading.value).toBe(false)
  expect(state.page.value?.items[0]?.title).toBe(articleFixture().title)
  finish({ items: [articleFixture({ title: '更新标题' })], total: 1, page: 1, page_size: 20 })
  await pending
  expect(state.page.value?.items[0]?.title).toBe('更新标题')
  expect(state.refreshing.value).toBe(false)
  scope.stop()
})
