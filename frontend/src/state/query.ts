import { CATEGORY_CODES } from '../api/contracts'
import type { ArticleQuery, CategoryFilter } from '../api/contracts'

export type QueryResult = { ok: true; value: ArticleQuery } | { ok: false; message: string }

const fields = [
  'q', 'category', 'region', 'product_type', 'date_from', 'date_to', 'page', 'page_size',
] as const
const accepted = new Set<string>(fields)

/** 严格验证来源日期，仅辨认日期，不推断上市或采集时间。 */
function parseDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false
  const [year, month, day] = match.slice(1).map(Number)
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > 31) return false
  const actual = new Date(0)
  actual.setUTCFullYear(year, month - 1, day)
  return actual.getUTCFullYear() === year && actual.getUTCMonth() === month - 1 &&
    actual.getUTCDate() === day
}

/** 解析地址栏中只读筛选字段；非法或重复值不能悄悄变成全部资讯。 */
export function decodeQuery(params: URLSearchParams): QueryResult {
  const seen = new Set<string>()
  const value: ArticleQuery = { page: 1, page_size: 20 }
  for (const [key, raw] of params) {
    if (!accepted.has(key) || seen.has(key)) return { ok: false, message: '筛选条件不可识别或重复' }
    seen.add(key)
    if (key === 'page' || key === 'page_size') {
      if (!/^[1-9]\d*$/.test(raw)) return { ok: false, message: '页码必须为正整数' }
      const number = Number(raw)
      if (!Number.isSafeInteger(number) || (key === 'page_size' && number > 100)) {
        return { ok: false, message: '分页参数超出支持范围' }
      }
      value[key] = number
    } else if (key === 'q') {
      if (Array.from(raw).length > 200) return { ok: false, message: '关键词不能超过 200 字符' }
      if (raw) value.q = raw
    } else if (key === 'category') {
      if (raw !== '__uncategorized__' && !CATEGORY_CODES.some((code) => code === raw)) {
        return { ok: false, message: '情报类别不存在' }
      }
      value.category = raw as CategoryFilter
    } else if (key === 'region' || key === 'product_type') {
      if (!raw || Array.from(raw).length > 100) return { ok: false, message: '筛选属性无效' }
      value[key] = raw
    } else if (key === 'date_from' || key === 'date_to') {
      if (!parseDate(raw)) return { ok: false, message: '报道日期无效' }
      value[key] = raw
    }
  }
  if (value.date_from && value.date_to && value.date_from > value.date_to) {
    return { ok: false, message: '起始日期不能晚于结束日期' }
  }
  return { ok: true, value }
}

/** URL 只保存阅读条件，省略默认页码，不包含密码、CSRF 或业务缓存。 */
export function encodeQuery(query: ArticleQuery): string {
  const encoded = new URLSearchParams()
  for (const key of fields) {
    const field = query[key]
    if (field === undefined || field === '' || (key === 'page' && field === 1) ||
      (key === 'page_size' && field === 20)) continue
    encoded.set(key, String(field))
  }
  return encoded.toString()
}

/** 更换交集条件后回到第一页；浏览器返回仍可由旧 URL 恢复原页。 */
export function changeFilters(current: ArticleQuery, patch: Partial<ArticleQuery>): ArticleQuery {
  return { ...current, ...patch, page: 1 }
}

/** 登录后仅允许返回已知页面和合法查询，不接受外站及变相开放跳转。 */
export function safeReturn(candidate: string): string {
  if (!candidate.startsWith('/') || candidate.startsWith('//') || /[\\\u0000-\u001f\u007f#]/.test(candidate)) return '/'
  const question = candidate.indexOf('?')
  const pathname = question < 0 ? candidate : candidate.slice(0, question)
  if (pathname !== '/' && pathname !== '/favorites') return '/'
  if (question < 0) return pathname
  try {
    const parsed = decodeQuery(new URLSearchParams(candidate.slice(question + 1)))
    if (!parsed.ok) return '/'
    const encoded = encodeQuery(parsed.value)
    return encoded ? `${pathname}?${encoded}` : pathname
  } catch {
    return '/'
  }
}
