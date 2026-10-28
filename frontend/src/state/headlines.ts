import { onScopeDispose, ref } from 'vue'
import type { Ref } from 'vue'
import { ApiError } from '../api/client'
import type { ApiClient } from '../api/client'
import type { ArticleOut, ArticlePage, ArticleQuery, FiltersOut } from '../api/contracts'
import type { SessionState } from './session'
import { encodeQuery } from './query'

interface HeadlinesOptions {
  api: ApiClient
  session: SessionState
  query: Ref<ArticleQuery>
  bookmarkedOnly: boolean
}

function isAbort(error: unknown): boolean {
  return typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError'
}

function explain(error: unknown): string {
  return error instanceof ApiError ? error.message : '资讯暂不可读取，请稍后重试'
}

/**
 * 读取服务器分页及动态选项。新筛选先撤掉旧列表，同条件失败仍保留最后成功页；
 * 旧请求和卸载后的回复不改动当前状态，也不复制整库到浏览器。
 */
export function useHeadlines({ api, session, query, bookmarkedOnly }: HeadlinesOptions) {
  const page = ref<ArticlePage | null>(null)
  const filters = ref<FiltersOut | null>(null)
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref<string | null>(null)
  let loadedKey: string | null = null
  let active: AbortController | null = null
  let generation = 0
  let disposed = false

  async function load(): Promise<void> {
    if (disposed) return
    const snapshot: ArticleQuery = { ...query.value }
    const key = encodeQuery(snapshot)
    active?.abort()
    const controller = new AbortController()
    active = controller
    const current = ++generation
    const sameQuery = page.value !== null && loadedKey === key
    if (!sameQuery) {
      page.value = null
      loading.value = true
      refreshing.value = false
    } else {
      loading.value = false
      refreshing.value = true
    }
    error.value = null

    // 筛选元信息和资讯并行读取，任一失败不伪造另一个成功结果。
    const articleRequest = session.protect(() => bookmarkedOnly
      ? api.listBookmarks(snapshot, controller.signal)
      : api.listArticles(snapshot, controller.signal))
    const filterRequest = session.protect(() => api.getFilters(controller.signal))
    const [articlesResult, filtersResult] = await Promise.allSettled([articleRequest, filterRequest])
    if (disposed || controller.signal.aborted || current !== generation) return

    // 任何受保护读取导致会话失效，都不能把旧的个人数据留在页面里。
    if (session.status.value !== 'authenticated') {
      page.value = null
      filters.value = null
      loadedKey = null
      const rejected = articlesResult.status === 'rejected' ? articlesResult : filtersResult
      error.value = rejected.status === 'rejected' ? explain(rejected.reason) : '请先登录'
      loading.value = false
      refreshing.value = false
      if (active === controller) active = null
      return
    }

    if (articlesResult.status === 'fulfilled') {
      page.value = articlesResult.value
      loadedKey = key
    } else if (!isAbort(articlesResult.reason)) {
      error.value = explain(articlesResult.reason)
    }
    if (filtersResult.status === 'fulfilled') {
      filters.value = filtersResult.value
    } else if (!isAbort(filtersResult.reason) && !error.value) {
      error.value = explain(filtersResult.reason)
    }
    loading.value = false
    refreshing.value = false
    if (active === controller) active = null
  }

  /** 用户确认后的同条件 GET 刷新；不能用于提交来源更新任务。 */
  function reload(): Promise<void> {
    return load()
  }

  /** 只同步服务端已确认的同一条目收藏标记，不在本地制造持久状态。 */
  function applyBookmark(articleId: number, confirmed: boolean): void {
    if (!page.value) return
    const items: ArticleOut[] = page.value.items.map((item) => item.id === articleId
      ? { ...item, bookmarked: confirmed }
      : item)
    page.value = { ...page.value, items }
  }

  onScopeDispose(() => {
    disposed = true
    generation += 1
    active?.abort()
    active = null
  })

  return { page, filters, loading, refreshing, error, load, reload, applyBookmark }
}
