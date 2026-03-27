import type { AnalysisReport, ContradictionResult, HistoryRow, ZenithReport } from './types'

const BASE = '/api/v1'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  return res.json()
}

export const api = {
  /**
   * Full 5-agent pipeline — returns AnalysisReport.
   * Used by the Alpha Analysis tab.
   */
  analyse: (ticker: string) =>
    post<AnalysisReport>('/alpha/analyse', { ticker, period: '1y' }),

  /**
   * Unified Zenith endpoint — GET /api/v1/alpha/analyze-stock?symbol=
   * Returns ZenithReport mapped for the dashboard panels.
   * Logs the raw response to the console for debugging.
   */
  analyzeStock: async (symbol: string): Promise<ZenithReport> => {
    const clean = symbol.trim().toUpperCase()
    console.debug(`[api.analyzeStock] → GET /alpha/analyze-stock?symbol=${clean}`)
    const data = await get<ZenithReport>(`/alpha/analyze-stock?symbol=${encodeURIComponent(clean)}`)
    console.debug('[api.analyzeStock] ← response:', data)

    // Guard against missing keys so UI never crashes on partial responses
    if (!data || typeof data.zenith_score !== 'number') {
      throw new Error(`Unexpected response shape for ${clean}: ${JSON.stringify(data)}`)
    }
    return data
  },

  contradict: (filing_text: string, news_text: string, ticker: string) =>
    post<ContradictionResult>('/analysis/contradict', { filing_text, news_text, ticker }),

  history: (ticker: string) =>
    get<{ results: HistoryRow[] }>(`/alpha/history/${ticker}`),

  latest: (ticker: string) =>
    get<HistoryRow>(`/alpha/latest/${ticker}`),
}
