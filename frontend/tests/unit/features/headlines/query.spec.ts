import { it, expect } from 'vitest'
import { decodeQuery, encodeQuery, changeFilters, safeReturn } from '../../../../src/features/headlines/query'

/** UNIT_ONLY：地址输入和返回路径使用合成值，不代表浏览器或服务端筛选已通过。 */
it('round-trips filters and rejects duplicate values and unsafe return paths', () => {
  expect(decodeQuery(new URLSearchParams('page=2&page=3')).ok).toBe(false)
  const parsed = decodeQuery(new URLSearchParams('q=100%25_&category=__uncategorized__&page=2'))
  if (!parsed.ok) throw new Error(parsed.message)
  expect(parsed.value.q).toBe('100%_')
  expect(changeFilters(parsed.value, { region: '__unknown__' }).page).toBe(1)
  expect(new URLSearchParams(encodeQuery(parsed.value)).get('category')).toBe('__uncategorized__')
  expect(safeReturn('//outside.example/x')).toBe('/')
  expect(safeReturn('/favorites?q=oil')).toBe('/favorites?q=oil')
})

it('keeps the seven server-defined categories and the missing-value markers separate', () => {
  const categories = [
    'new_products', 'trends', 'new_ingredients', 'research_technology',
    'packaging_formulation', 'oem_odm', 'regulation_compliance',
  ]
  for (const category of categories) {
    const result = decodeQuery(new URLSearchParams({ category }))
    expect(result.ok, category).toBe(true)
    if (result.ok) expect(result.value.category).toBe(category)
  }
  const unknown = decodeQuery(new URLSearchParams('category=__uncategorized__&region=__unknown__&product_type=__unknown__'))
  expect(unknown.ok).toBe(true)
  if (unknown.ok) {
    expect(unknown.value.category).toBe('__uncategorized__')
    expect(unknown.value.region).toBe('__unknown__')
  }
  expect(decodeQuery(new URLSearchParams('category=all')).ok).toBe(false)
})

it('accepts actual leap days and rejects invalid ranges without making up a report date', () => {
  expect(decodeQuery(new URLSearchParams('date_from=2024-02-29&date_to=2024-03-01')).ok).toBe(true)
  for (const query of ['date_from=2025-02-29', 'date_from=2025-04-31',
    'date_from=2026-10-28&date_to=2026-10-27']) {
    expect(decodeQuery(new URLSearchParams(query)).ok, query).toBe(false)
  }
})

it('rejects invalid pagination, unknown keys and off-site returns without clearing a valid filter', () => {
  for (const query of ['page=0', 'page=01', 'page_size=101', 'q=' + 'a'.repeat(201),
    'secret=abc', 'region=a&region=b']) {
    expect(decodeQuery(new URLSearchParams(query)).ok, query).toBe(false)
  }
  for (const unsafe of ['https://evil.example/', '/\\evil', '/login', '/favorites?redirect=https://evil.example',
    '/favorites#logout', '/other', '/favorites/../login']) {
    expect(safeReturn(unsafe), unsafe).toBe('/')
  }
  expect(safeReturn('/favorites?q=100%25_')).toBe('/favorites?q=100%25_')
})
