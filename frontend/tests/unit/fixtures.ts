// UNIT_ONLY：仅供组件及 HTTP 适配单元测试，不得导入 src 或真实 browser E2E。
import type {
  ArticleOut, AuthOut, FiltersOut, JobOut, SourceOut,
} from '../../src/shared/api/contracts'

/** 与已确认 DTO 对齐的合成条目；不能代表来源使用许可或真实资讯。 */
export function articleFixture(overrides: Partial<ArticleOut> = {}): ArticleOut {
  return {
    id: 7,
    title: 'UNIT_ONLY：合成标题',
    source: { id: 1, key: 'unit', name: 'UNIT_ONLY 来源', language: null },
    original_url: 'https://unit.example/article/7',
    reported_date: null,
    category_codes: [],
    region: null,
    product_type: null,
    image_url: null,
    image_credit: null,
    updated_at: '2026-01-01T00:00:00Z',
    bookmarked: false,
    ...overrides,
  }
}

export function authFixture(): AuthOut {
  return { authenticated: true, expires_at: '2026-01-02T00:00:00Z', csrf_token: 'unit-csrf' }
}

export function filtersFixture(): FiltersOut {
  return {
    categories: [
      { value: 'new_products', label: '新品发布' },
      { value: 'trends', label: '趋势洞察' },
      { value: 'new_ingredients', label: '新原料' },
      { value: 'research_technology', label: '研发技术' },
      { value: 'packaging_formulation', label: '包装与剂型' },
      { value: 'oem_odm', label: 'OEM／ODM' },
      { value: 'regulation_compliance', label: '法规与合规' },
    ],
    regions: [], product_types: [],
    uncategorized_value: '__uncategorized__', unknown_value: '__unknown__',
  }
}

export function sourceFixture(overrides: Partial<SourceOut> = {}): SourceOut {
  return {
    id: 1, key: 'unit', name: 'UNIT_ONLY 来源', language: null,
    verification_status: 'pending', reason: null,
    entries: [{
      id: 1, url: 'https://unit.example/feed', kind: 'rss',
      verification_status: 'pending', verification_reason: null,
      verification_reference: null, enabled: false, last_success_at: null, last_error: null,
    }],
    ...overrides,
  }
}

export function jobFixture(overrides: Partial<JobOut> = {}): JobOut {
  return {
    id: 1, trigger: 'refresh', state: 'pending', schedule_date: null,
    created_at: '2026-01-01T00:00:00Z', started_at: null, finished_at: null,
    count_added: 0, count_updated: 0, entries: [],
    ...overrides,
  }
}
