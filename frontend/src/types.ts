export type Signal = 'STRONG_BUY' | 'BUY' | 'NEUTRAL' | 'SELL' | 'STRONG_SELL'

// ── Zenith unified response ───────────────────────────────────────────────

export interface NarrativeConflict {
  level:   'NONE' | 'LOW' | 'MEDIUM' | 'STRONG' | 'CRITICAL'
  summary: string
  points:  string[]
}

export interface SentimentDivergence {
  retail_sentiment: number   // -1 to +1
  insider_activity: number   // -1 to +1
  signal: 'ALIGNED' | 'DIVERGING' | 'MANIPULATION RISK'
}

export interface QuantInsight {
  pattern:      string
  success_rate: number   // 0–100
  confidence:   number   // 0.0–1.0
}

export interface ZenithReport {
  symbol:               string
  zenith_score:         number   // 0–100
  signal:               string   // 'STRONG BUY' | 'BUY' | 'NEUTRAL' | 'SELL' | 'STRONG SELL'
  narrative_conflict:   NarrativeConflict
  sentiment_divergence: SentimentDivergence
  quant_insight:        QuantInsight
}

export interface AgentResult {
  agent: string
  success: boolean
  score: number | null
  data: Record<string, unknown>
  error: string | null
}

export interface AnalysisReport {
  ticker: string
  company_name: string
  alpha_score: number
  signal: Signal
  signal_emoji: string
  summary: string
  key_risks: string[]
  agent_results: Record<string, AgentResult>
  weights_used: Record<string, number>
  agents_failed: string[]
  duration_ms: number
}

export interface ContradictionResult {
  contradiction_level: 'none' | 'low' | 'medium' | 'high' | 'critical'
  contradictions: string[]
  explanation: string
  risk_summary: string
}

export interface HistoryRow {
  id: string
  ticker: string
  company_name: string
  alpha_score: number
  signal: Signal
  summary: string
  key_risks: string[]
  created_at: string
}
