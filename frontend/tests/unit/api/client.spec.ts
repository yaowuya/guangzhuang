import { it, expect, vi } from 'vitest'
import { createApi, ApiError } from '../../../src/shared/api/client'
import { articleFixture, jobFixture, sourceFixture } from '../fixtures'

/** UNIT_ONLY：只替换浏览器 fetch 边界，不作为真实服务或 E2E 证据。 */
it('sends a same-origin confirmed write once and preserves errors', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ code: 'storage_unavailable', message: '暂不可用', request_id: 'unit-1' }),
    { status: 503, headers: { 'Content-Type': 'application/json' } },
  ))
  const api = createApi(fetcher)
  await expect(api.setBookmark(7, false, 'unit-csrf')).rejects.toBeInstanceOf(ApiError)
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/bookmarks/7')
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
    method: 'DELETE', credentials: 'same-origin', body: undefined,
    headers: expect.objectContaining({ 'X-CSRF-Token': 'unit-csrf' }),
  })
})

it('preserves cancellation while reading a response rather than misreporting an API error', async () => {
  const abort = new DOMException('cancelled', 'AbortError')
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: () => Promise.reject(abort),
  } as Response)
  await expect(createApi(fetcher).listArticles()).rejects.toBe(abort)
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('does not accept an unconfirmed login result as a valid session', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ authenticated: false }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))
  await expect(createApi(fetcher).login('unit-password')).rejects.toMatchObject({
    code: 'invalid_response',
  })
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/auth/login')
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
    method: 'POST', credentials: 'same-origin', body: JSON.stringify({ password: 'unit-password' }),
  })
  expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty('X-CSRF-Token')
})

it('does not accept an unconfirmed logout result as a revoked session', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ authenticated: true }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))
  await expect(createApi(fetcher).logout('unit-csrf')).rejects.toMatchObject({
    code: 'invalid_response',
  })
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/auth/logout')
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
    method: 'POST', body: JSON.stringify({}),
    headers: expect.objectContaining({ 'X-CSRF-Token': 'unit-csrf' }),
  })
})

it('requires a service-confirmed bookmark flag on every list item', async () => {
  const { bookmarked: _omitted, ...item } = articleFixture()
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ items: [item], total: 1, page: 1, page_size: 20 }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))
  await expect(createApi(fetcher).listArticles()).rejects.toMatchObject({ code: 'invalid_response' })
})

it('rejects incomplete or negative article page fields', async () => {
  const malformed = {
    items: [{ id: -1, title: 'x', original_url: 'x', source: { name: 's' }, bookmarked: false }],
    total: -1, page: 0, page_size: 0,
  }
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify(malformed),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))
  await expect(createApi(fetcher).listArticles()).rejects.toMatchObject({ code: 'invalid_response' })
})

it('rejects incomplete source and job response contracts', async () => {
  const json = (body: unknown) => new Response(JSON.stringify(body), {
    status: 200, headers: { 'Content-Type': 'application/json' },
  })
  const source = sourceFixture()
  const entry = {
    entry_id: 1, source_id: 1, source_name: 'UNIT',
    state: 'succeeded', count_added: 0, count_updated: 0, error: null, finished_at: null,
  }
  const fetcher = vi.fn<typeof fetch>()
    .mockResolvedValueOnce(json({ items: [{ ...source, entries: [{ ...source.entries[0], url: undefined }] }] }))
    .mockResolvedValueOnce(json({ job: { ...jobFixture({ count_added: -1 }), entries: [entry] }, reused: false }))
  const api = createApi(fetcher)
  await expect(api.listSources()).rejects.toMatchObject({ code: 'invalid_response' })
  await expect(api.createJob('unit-csrf')).rejects.toMatchObject({ code: 'invalid_response' })
})

it('keeps site and entry verification statuses separate', async () => {
  const source = sourceFixture({ verification_status: 'partial' })
  const invalidEntry = { ...source.entries[0], verification_status: 'partial' }
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ items: [{ ...source, entries: [invalidEntry] }] }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))
  await expect(createApi(fetcher).listSources()).rejects.toMatchObject({ code: 'invalid_response' })
})

it('rejects a job result without a confirmed boolean reused state', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ job: jobFixture(), reused: 'false' }),
    { status: 202, headers: { 'Content-Type': 'application/json' } },
  ))
  await expect(createApi(fetcher).createJob('unit-csrf')).rejects.toMatchObject({ code: 'invalid_response' })
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/update-jobs')
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
    method: 'POST', body: JSON.stringify({ trigger: 'refresh' }),
    headers: expect.objectContaining({ 'X-CSRF-Token': 'unit-csrf' }),
  })
})

it('keeps new, reused and no-current-job outcomes distinct', async () => {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  })
  const fetcher = vi.fn<typeof fetch>()
    .mockResolvedValueOnce(json({ job: jobFixture(), reused: false }, 202))
    .mockResolvedValueOnce(json({ job: jobFixture(), reused: true }, 200))
    .mockResolvedValueOnce(json({ job: null }))
  const api = createApi(fetcher)
  expect((await api.createJob('unit-csrf')).reused).toBe(false)
  expect((await api.retryJob(1, 'unit-csrf')).reused).toBe(true)
  expect((await api.getCurrentJob()).job).toBeNull()
  expect(fetcher.mock.calls[1]?.[0]).toBe('/api/update-jobs/1/retry')
  expect(fetcher.mock.calls[2]?.[0]).toBe('/api/update-jobs/current')
})

it('keeps filtering URL-encoded and uses confirmed source/entry status', async () => {
  const json = (body: unknown) => new Response(JSON.stringify(body), {
    status: 200, headers: { 'Content-Type': 'application/json' },
  })
  const source = sourceFixture({ verification_status: 'partial' })
  const fetcher = vi.fn<typeof fetch>()
    .mockResolvedValueOnce(json({ items: [articleFixture()], total: 1, page: 2, page_size: 20 }))
    .mockResolvedValueOnce(json({ items: [source] }))
  const api = createApi(fetcher)
  const page = await api.listArticles({ q: '100%_', category: '__uncategorized__', page: 2 })
  expect(page.items[0]?.bookmarked).toBe(false)
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/articles?q=100%25_&category=__uncategorized__&page=2')
  const [listed] = await api.listSources()
  expect(listed.verification_status).toBe('partial')
  expect(listed.entries[0]?.verification_status).toBe('pending')
})

it('rejects filter metadata without fixed missing-value sentinels', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify({ categories: [], regions: [], product_types: [], uncategorized_value: 'ALL' }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  ))
  await expect(createApi(fetcher).getFilters()).rejects.toMatchObject({ code: 'invalid_response' })
})