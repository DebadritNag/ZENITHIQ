/**
 * ZenithDashboard
 * ---------------
 * Full dashboard view for a single stock analysis.
 * Calls GET /api/v1/alpha/analyze-stock?symbol= and renders
 * the four panels: ZenithScore, NarrativeConflict,
 * SentimentDivergence, QuantInsight.
 */

import { useState } from 'react'
import { Search, RefreshCw } from 'lucide-react'
import { api } from '../api'
import type { ZenithReport } from '../types'
import { ZenithScore } from './ZenithScore'
import { NarrativeConflictPanel } from './NarrativeConflictPanel'
import { SentimentDivergencePanel } from './SentimentDivergencePanel'
import { QuantInsightPanel } from './QuantInsightPanel'

export function ZenithDashboard() {
  const [symbol, setSymbol]   = useState('')
  const [report, setReport]   = useState<ZenithReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  const run = async (sym: string) => {
    const clean = sym.trim().toUpperCase()
    if (!clean) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.analyzeStock(clean)
      setReport(data)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Analysis failed'
      console.error('[ZenithDashboard] error:', e)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = () => run(symbol)
  const handleKey    = (e: React.KeyboardEvent) => { if (e.key === 'Enter') run(symbol) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Search bar */}
      <div style={{ display: 'flex', gap: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, padding: '8px 12px', border: '1px solid #2B2F36', borderRight: 'none', background: '#0B0E11' }}>
          <Search size={13} color="#5A6070" />
          <input
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Enter symbol — RELIANCE, TCS, AAPL..."
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              fontFamily: 'JetBrains Mono,monospace', fontSize: 12, color: '#E8EAF0',
            }}
          />
        </div>
        <button
          onClick={handleSubmit}
          disabled={loading || !symbol.trim()}
          style={{
            padding: '8px 20px', background: loading ? '#2B2F36' : '#E31B23',
            color: '#fff', border: '1px solid #E31B23',
            fontFamily: 'JetBrains Mono,monospace', fontSize: 11, fontWeight: 700,
            letterSpacing: '0.1em', cursor: loading || !symbol.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !symbol.trim() ? 0.6 : 1,
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          {loading
            ? <><RefreshCw size={11} style={{ animation: 'spin 1s linear infinite' }} /> ANALYSING</>
            : '▶ ANALYSE'
          }
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '8px 12px', border: '1px solid #E31B23', background: '#3D0A0C',
          fontFamily: 'JetBrains Mono,monospace', fontSize: 11, color: '#E31B23',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span>✗ {error}</span>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: '#E31B23', cursor: 'pointer', fontSize: 12 }}>✕</button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {[0, 1, 2, 3].map(i => (
            <div key={i} style={{ border: '1px solid #2B2F36', background: '#131720', padding: 20, height: 140 }}>
              <div style={{ height: 8, width: '40%', background: '#2B2F36', marginBottom: 12, animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: 40, width: '60%', background: '#1A1F2E', animation: 'pulse 1.5s ease-in-out infinite' }} />
            </div>
          ))}
        </div>
      )}

      {/* Dashboard panels */}
      {!loading && report && (
        <>
          {/* Row 1: Score + Conflict */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div id="tour-zenith-score">
              <ZenithScore score={report.zenith_score} signal={report.signal} symbol={report.symbol} />
            </div>
            <div id="tour-narrative-conflict">
              <NarrativeConflictPanel data={report.narrative_conflict} />
            </div>
          </div>

          {/* Row 2: Sentiment + Quant */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div id="tour-sentiment">
              <SentimentDivergencePanel data={report.sentiment_divergence} />
            </div>
            <div id="tour-quant-insight">
              <QuantInsightPanel data={report.quant_insight} />
            </div>
          </div>

          {/* Raw JSON debug (collapsed by default) */}
          <details style={{ border: '1px solid #2B2F36', background: '#0B0E11' }}>
            <summary style={{ padding: '6px 12px', fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color: '#5A6070', cursor: 'pointer', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Raw API Response (debug)
            </summary>
            <pre style={{ padding: 12, fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#5A6070', overflowX: 'auto', margin: 0 }}>
              {JSON.stringify(report, null, 2)}
            </pre>
          </details>
        </>
      )}

      {/* Empty state */}
      {!loading && !report && !error && (
        <div style={{ padding: '48px 0', textAlign: 'center' }}>
          <div style={{ fontFamily: 'Playfair Display,serif', fontSize: 32, color: '#2B2F36', marginBottom: 8 }}>ZENITH</div>
          <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#3A3F4A', letterSpacing: '0.15em' }}>
            ENTER A SYMBOL TO BEGIN ANALYSIS
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 20 }}>
            {['RELIANCE', 'TCS', 'AAPL', 'TSLA'].map(s => (
              <button key={s} onClick={() => { setSymbol(s); run(s) }}
                style={{
                  padding: '4px 10px', border: '1px solid #2B2F36', background: 'transparent',
                  fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#5A6070',
                  cursor: 'pointer',
                }}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
