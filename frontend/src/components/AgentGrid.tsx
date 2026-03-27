import type { AgentResult } from '../types'

const AGENT_ICONS: Record<string, string> = {
  FilingAgent:    '📄',
  NewsAgent:      '📰',
  SentimentAgent: '💬',
  InsiderAgent:   '👤',
  QuantAgent:     '📈',
}

const AGENT_DESC: Record<string, string> = {
  FilingAgent:    'SEC EDGAR · 10-K / 10-Q',
  NewsAgent:      'NewsAPI · Scraped Headlines',
  SentimentAgent: 'Reddit · RoBERTa FinBERT',
  InsiderAgent:   'OpenInsider · Buy/Sell',
  QuantAgent:     'yfinance · H&S · Breakout',
}

export function AgentGrid({ results }: { results: Record<string, AgentResult> }) {
  return (
    <div>
      <div className="px-4 py-2 flex items-center justify-between"
        style={{ borderBottom: '1px solid #2B2F36', background: '#0B0E11' }}>
        <span className="text-[10px] tracking-widest uppercase"
          style={{ color: '#E8EAF0', fontFamily: 'JetBrains Mono, monospace' }}>
          ◈ Agent Intelligence Grid
        </span>
        <span className="text-[10px]"
          style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
          {Object.values(results).filter(r => r.success).length} / {Object.keys(results).length} succeeded
        </span>
      </div>
      <div className="grid grid-cols-5">
        {Object.entries(results).map(([name, res], idx) => (
          <AgentCell key={name} name={name} result={res}
            isLast={idx === Object.keys(results).length - 1} />
        ))}
      </div>
    </div>
  )
}

function AgentCell({
  name, result, isLast,
}: { name: string; result: AgentResult; isLast: boolean }) {
  const score = result.score ?? 0.5
  const pct   = Math.round(score * 100)
  const color = score >= 0.6 ? '#00C805' : score >= 0.45 ? '#F59E0B' : '#E31B23'
  const icon  = AGENT_ICONS[name] ?? '◈'
  const desc  = AGENT_DESC[name] ?? ''
  const highlight = getHighlight(name, result.data)

  return (
    <div className="p-4"
      style={{ borderRight: isLast ? 'none' : '1px solid #2B2F36', background: '#131720' }}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-base">{icon}</span>
        <div>
          <div className="text-[10px] font-semibold"
            style={{ fontFamily: 'JetBrains Mono, monospace', color: '#E8EAF0' }}>
            {name.replace('Agent', '')}
          </div>
          <div className="text-[9px]"
            style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>{desc}</div>
        </div>
      </div>
      <div className="text-3xl font-bold mb-1"
        style={{ color, fontFamily: 'JetBrains Mono, monospace' }}>{pct}</div>
      <div className="h-px w-full mb-3" style={{ background: '#2B2F36' }}>
        <div style={{ width: `${pct}%`, background: color, height: '100%' }} />
      </div>
      <div className="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 mb-2"
        style={{
          border: `1px solid ${result.success ? '#00C805' : '#E31B23'}`,
          color: result.success ? '#00C805' : '#E31B23',
          fontFamily: 'JetBrains Mono, monospace',
        }}>
        {result.success ? '✓ OK' : '✗ FAILED'}
      </div>
      {highlight && (
        <div className="text-[9px] leading-relaxed"
          style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>{highlight}</div>
      )}
      {result.error && (
        <div className="text-[9px] mt-1"
          style={{ color: '#E31B23', fontFamily: 'JetBrains Mono, monospace' }}>
          {result.error.slice(0, 80)}
        </div>
      )}
    </div>
  )
}

function getHighlight(name: string, data: Record<string, unknown>): string {
  if (!data) return ''
  try {
    if (name === 'FilingAgent') {
      return `Form: ${data.form_type ?? '—'} · ${data.filing_date ?? ''}`
    }
    if (name === 'NewsAgent') {
      const h = data.headlines as string[] | undefined
      return h?.[0] ? `"${h[0].slice(0, 60)}..."` : `${data.article_count ?? 0} articles`
    }
    if (name === 'SentimentAgent') {
      return `${data.label ?? '—'} · ${data.post_count ?? 0} posts · score ${data.sentiment_score ?? '—'}`
    }
    if (name === 'InsiderAgent') {
      const s = data.summary as Record<string, number> | undefined
      if (s) return `Buys: ${s.buy_count ?? 0} · Sells: ${s.sell_count ?? 0}`
    }
    if (name === 'QuantAgent') {
      const ind = data.indicators as Record<string, unknown> | undefined
      if (ind) return `RSI ${ind.rsi} · ${ind.rsi_signal} · MACD ${ind.macd_bullish ? '▲' : '▼'}`
    }
  } catch { /* ignore */ }
  return ''
}
