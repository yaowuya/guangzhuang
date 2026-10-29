/** 仅描述已确认的后端 HTTP 数据；不含正文、摘要或原型样本。 */
export const CATEGORY_CODES = [
  'new_products', 'trends', 'new_ingredients', 'research_technology',
  'packaging_formulation', 'oem_odm', 'regulation_compliance',
] as const

export type CategoryCode = typeof CATEGORY_CODES[number]
export type CategoryFilter = CategoryCode | '__uncategorized__'
export type EntryKind = 'rss' | 'public_list'
export type EntryVerification = 'pending' | 'allowed' | 'restricted'
export type SourceVerification = EntryVerification | 'partial'
export type JobTrigger = 'schedule' | 'catchup' | 'refresh' | 'retry'
export type JobState = 'pending' | 'running' | 'succeeded' | 'partial' | 'failed' | 'interrupted'
export type EntryResultState = Exclude<JobState, 'partial'>

export interface AuthOut {
  authenticated: true
  expires_at: string
  csrf_token: string
}

export interface ErrorOut {
  code: string
  message: string
  request_id: string
}

export interface SourceRef {
  id: number
  key: string
  name: string
  language: string | null
}

export interface ArticleOut {
  id: number
  title: string
  source: SourceRef
  original_url: string
  reported_date: string | null
  category_codes: CategoryCode[]
  region: string | null
  product_type: string | null
  image_url: string | null
  image_credit: string | null
  updated_at: string
  bookmarked: boolean
}

export interface ArticlePage {
  items: ArticleOut[]
  total: number
  page: number
  page_size: number
}

export interface ArticleQuery {
  q?: string
  category?: CategoryFilter
  region?: string
  product_type?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface FilterOption<T extends string = string> {
  value: T
  label: string
}

export interface FiltersOut {
  categories: FilterOption<CategoryCode>[]
  regions: FilterOption[]
  product_types: FilterOption[]
  uncategorized_value: '__uncategorized__'
  unknown_value: '__unknown__'
}

export interface BookmarkOut {
  article_id: number
  bookmarked: boolean
}

export interface EntryOut {
  id: number
  url: string
  kind: EntryKind
  verification_status: EntryVerification
  verification_reason: string | null
  verification_reference: string | null
  enabled: boolean
  last_success_at: string | null
  last_error: string | null
}

export interface SourceOut extends SourceRef {
  verification_status: SourceVerification
  reason: string | null
  entries: EntryOut[]
}

export interface EntryResultOut {
  entry_id: number
  source_id: number
  source_name: string
  entry_url: string
  state: EntryResultState
  count_added: number
  count_updated: number
  error: string | null
  finished_at: string | null
}

export interface JobOut {
  id: number
  trigger: JobTrigger
  state: JobState
  schedule_date: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  count_added: number
  count_updated: number
  entries: EntryResultOut[]
}

export interface EnqueueOut {
  job: JobOut
  reused: boolean
}

export interface CurrentJobOut {
  job: JobOut | null
}
