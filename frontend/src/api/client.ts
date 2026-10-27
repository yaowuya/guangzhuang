import { CATEGORY_CODES } from './contracts'
import type {
  ArticleOut, ArticlePage, ArticleQuery, AuthOut, BookmarkOut, CurrentJobOut,
  EnqueueOut, FiltersOut, JobOut, SourceOut,
} from './contracts'

/** API 错误保留后端状态和请求标识，但不回显原始响应或私密请求。 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly request_id: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** DOMException 可来自另一个 JS realm；按名称保留用户取消，不按 Error instanceof 判断。 */
function isAbort(error: unknown): boolean {
  return isRecord(error) && error.name === 'AbortError'
}

function validId(id: number): number {
  if (!Number.isSafeInteger(id) || id < 1) {
    throw new ApiError(400, 'bad_request', '条目标识无效', '')
  }
  return id
}

function confirmedArticle(value: unknown): value is ArticleOut {
  return isRecord(value) && Number.isSafeInteger(value.id) &&
    typeof value.title === 'string' && typeof value.original_url === 'string' &&
    isRecord(value.source) && typeof value.source.name === 'string' &&
    typeof value.bookmarked === 'boolean'
}

/** 列表中每项的收藏状态必须由服务器确认，不能由当前页面猜测。 */
function confirmedPage(page: ArticlePage, bookmarkedOnly: boolean): ArticlePage {
  if (!Array.isArray(page.items) || !Number.isSafeInteger(page.total) ||
    !Number.isSafeInteger(page.page) || !Number.isSafeInteger(page.page_size) ||
    !page.items.every((item) => confirmedArticle(item) && (!bookmarkedOnly || item.bookmarked))) {
    throw new ApiError(200, 'invalid_response', '资讯列表不可读取', '')
  }
  return page
}

function confirmedJob(value: unknown): value is JobOut {
  const states = ['pending', 'running', 'succeeded', 'partial', 'failed', 'interrupted']
  const entryStates = ['pending', 'running', 'succeeded', 'failed', 'interrupted']
  return isRecord(value) && Number.isSafeInteger(value.id) &&
    states.includes(value.state as string) && Array.isArray(value.entries) &&
    value.entries.every((entry: unknown) => isRecord(entry) &&
      Number.isSafeInteger(entry.entry_id) && entryStates.includes(entry.state as string)) &&
    Number.isSafeInteger(value.count_added) && Number.isSafeInteger(value.count_updated)
}

function confirmedEnqueue(value: EnqueueOut): EnqueueOut {
  if (!confirmedJob(value.job) || typeof value.reused !== 'boolean') {
    throw new ApiError(200, 'invalid_response', '更新任务尚未确认', '')
  }
  return value
}

function params(query: ArticleQuery): string {
  const result = new URLSearchParams()
  const keys = [
    'q', 'category', 'region', 'product_type', 'date_from', 'date_to',
    'page', 'page_size',
  ] as const
  for (const key of keys) {
    const value = query[key]
    if (value !== undefined && value !== '') result.set(key, String(value))
  }
  const encoded = result.toString()
  return encoded ? `?${encoded}` : ''
}

/** 提供固定同源业务方法；不公开任意 URL 请求，不自动重试写操作。 */
export function createApi(fetcher: typeof fetch = globalThis.fetch) {
  async function request<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET',
    options: { data?: object; csrf?: string; signal?: AbortSignal } = {},
  ): Promise<T> {
    const hasBody = options.data !== undefined
    const headers: Record<string, string> = {}
    if (hasBody) headers['Content-Type'] = 'application/json'
    if (options.csrf !== undefined) headers['X-CSRF-Token'] = options.csrf
    let response: Response
    try {
      response = await fetcher(path, {
        method,
        credentials: 'same-origin',
        headers,
        body: hasBody ? JSON.stringify(options.data) : undefined,
        signal: options.signal,
      })
    } catch (error) {
      if (isAbort(error)) throw error
      throw new ApiError(0, 'network_unavailable', '网络暂不可用，请稍后重试', '')
    }
    let value: unknown
    try {
      if (!response.headers.get('Content-Type')?.toLowerCase().includes('application/json')) {
        throw new Error('unexpected media type')
      }
      value = await response.json()
    } catch (error) {
      if (isAbort(error)) throw error
      throw new ApiError(response.status, 'invalid_response', '服务响应不可读取', '')
    }
    if (!response.ok) {
      if (isRecord(value) && typeof value.code === 'string' && value.code &&
        typeof value.message === 'string' && value.message &&
        typeof value.request_id === 'string' && value.request_id) {
        throw new ApiError(response.status, value.code, value.message, value.request_id)
      }
      throw new ApiError(response.status, 'invalid_response', '请求未完成，请稍后重试', '')
    }
    if (!isRecord(value)) throw new ApiError(response.status, 'invalid_response', '服务响应不可读取', '')
    return value as T
  }

  return {
    async login(password: string): Promise<AuthOut> {
      // 首次登录尚无服务器会话，绝不附加旧的 CSRF。浏览器自行发送同源 Origin。
      const result = await request<AuthOut>('/api/auth/login', 'POST', { data: { password } })
      if (result.authenticated !== true || typeof result.expires_at !== 'string' || !result.expires_at ||
        typeof result.csrf_token !== 'string' || !result.csrf_token) {
        throw new ApiError(200, 'invalid_response', '登录结果尚未确认', '')
      }
      return result
    },
    async getSession(signal?: AbortSignal): Promise<AuthOut> {
      const result = await request<AuthOut>('/api/auth/session', 'GET', { signal })
      if (result.authenticated !== true || typeof result.expires_at !== 'string' || !result.expires_at ||
        typeof result.csrf_token !== 'string' || !result.csrf_token) {
        throw new ApiError(200, 'invalid_response', '会话状态尚未确认', '')
      }
      return result
    },
    logout(csrf: string): Promise<{ authenticated: false }> {
      return request<{ authenticated: false }>('/api/auth/logout', 'POST', { data: {}, csrf })
    },
    async listArticles(query: ArticleQuery = {}, signal?: AbortSignal): Promise<ArticlePage> {
      const page = await request<ArticlePage>(`/api/articles${params(query)}`, 'GET', { signal })
      return confirmedPage(page, false)
    },
    async getArticle(id: number, signal?: AbortSignal): Promise<ArticleOut> {
      const article = await request<ArticleOut>(`/api/articles/${validId(id)}`, 'GET', { signal })
      if (!confirmedArticle(article)) throw new ApiError(200, 'invalid_response', '资讯详情不可读取', '')
      return article
    },
    async getFilters(signal?: AbortSignal): Promise<FiltersOut> {
      const result = await request<FiltersOut>('/api/filters', 'GET', { signal })
      const validOptions = (options: unknown) => Array.isArray(options) &&
        options.every((option: unknown) => isRecord(option) &&
          typeof option.value === 'string' && typeof option.label === 'string')
      if (result.uncategorized_value !== '__uncategorized__' || result.unknown_value !== '__unknown__' ||
        !validOptions(result.categories) || !validOptions(result.regions) ||
        !validOptions(result.product_types) ||
        !CATEGORY_CODES.every((code) => result.categories.some((option) => option.value === code))) {
        throw new ApiError(200, 'invalid_response', '筛选选项不可读取', '')
      }
      return result
    },
    async listBookmarks(query: ArticleQuery = {}, signal?: AbortSignal): Promise<ArticlePage> {
      const page = await request<ArticlePage>(`/api/bookmarks${params(query)}`, 'GET', { signal })
      return confirmedPage(page, true)
    },
    async setBookmark(id: number, value: boolean, csrf: string): Promise<BookmarkOut> {
      const articleId = validId(id)
      const result = await request<BookmarkOut>(
        `/api/bookmarks/${articleId}`, value ? 'PUT' : 'DELETE',
        { data: value ? {} : undefined, csrf },
      )
      // 收藏的服务端确认必须与本次动作吻合；错误状态不乐观写入 UI。
      if (result.article_id !== articleId || result.bookmarked !== value) {
        throw new ApiError(200, 'invalid_response', '收藏状态尚未确认', '')
      }
      return result
    },
    async listSources(signal?: AbortSignal): Promise<SourceOut[]> {
      const result = await request<{ items: SourceOut[] }>('/api/sources', 'GET', { signal })
      const entryStates = ['pending', 'allowed', 'restricted']
      const siteStates = [...entryStates, 'partial']
      if (!Array.isArray(result.items) || !result.items.every((source) =>
        isRecord(source) && Number.isSafeInteger(source.id) &&
        typeof source.key === 'string' && typeof source.name === 'string' &&
        siteStates.includes(source.verification_status as string) &&
        Array.isArray(source.entries) && source.entries.every((entry: unknown) =>
          isRecord(entry) && Number.isSafeInteger(entry.id) &&
          entryStates.includes(entry.verification_status as string) &&
          typeof entry.enabled === 'boolean'))) {
        throw new ApiError(200, 'invalid_response', '来源状态不可读取', '')
      }
      return result.items
    },
    async createJob(csrf: string): Promise<EnqueueOut> {
      const result = await request<EnqueueOut>('/api/update-jobs', 'POST', {
        data: { trigger: 'refresh' }, csrf,
      })
      return confirmedEnqueue(result)
    },
    async retryJob(id: number, csrf: string): Promise<EnqueueOut> {
      const result = await request<EnqueueOut>(`/api/update-jobs/${validId(id)}/retry`, 'POST', {
        data: {}, csrf,
      })
      return confirmedEnqueue(result)
    },
    async getCurrentJob(signal?: AbortSignal): Promise<CurrentJobOut> {
      const result = await request<CurrentJobOut>('/api/update-jobs/current', 'GET', { signal })
      if (!('job' in result) || (result.job !== null && !confirmedJob(result.job))) {
        throw new ApiError(200, 'invalid_response', '更新状态不可读取', '')
      }
      return result
    },
    async getJob(id: number, signal?: AbortSignal): Promise<JobOut> {
      const result = await request<JobOut>(`/api/update-jobs/${validId(id)}`, 'GET', { signal })
      if (!confirmedJob(result)) throw new ApiError(200, 'invalid_response', '更新状态不可读取', '')
      return result
    },
  }
}

export type ApiClient = ReturnType<typeof createApi>
