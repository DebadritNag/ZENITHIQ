import { useState, useEffect, useRef } from 'react'
import { FileText, Rss, Cpu, AlertTriangle, CheckCircle } from 'lucide-react'
import { api } from '../api'
import type { ContradictionResult } from '../types'

const LEVEL_CFG = {
  none:     { color: '#00C805', label: 'NO CONFLICT',         pct: 0   },
  low:      { color: '#F59E0B', label: 'LOW TENSION',         pct: 20  },
  medium:   { color: '#F59E0B', label: 'NOTABLE DIVERGENCE',  pct: 50  },
  high:     { color: '#E31B23', label: 'HIGH CONFLICT',       pct: 75  },
  critical: { color: '#E31B23', label: 'BULL-SHIFT DETECTED', pct: 100 },
}

const DEMO_FILING = `ANNUAL REPORT FY2025 — MANAGEMENT DISCUSSION

§ 4.2 Margin Outlook
"We expect 20% margin growth in FY2026, driven by our cloud infrastructure expansion and operational efficiency programs. Management remains confident in sustained double-digit revenue growth across all verticals."

§ 4.3 Capital Allocation
"The Board has approved a buyback program, reflecting our strong cash position and confidence in long-term value creation."`

const DEMO_NEWS = `ET MARKETS — 2 HOURS AGO
Company cuts margin guidance to 5% amid rising input costs. CFO cites "unexpected headwinds" in Q3 earnings call.

BLOOMBERG — 4 HOURS AGO
Three C-suite executives sold shares worth $4M in the past 30 days, SEC filings reveal.

REUTERS — 6 HOURS AGO
Analysts downgrade to SELL. Price target cut 35%. "Guidance credibility at risk."`

const TERMINAL_LINES = [
  '> INITIALIZING CONTRADICTION MATRIX...',
  '> LOADING FILING VECTORS FROM SUPABASE...',
  '> CROSS-REFERENCING NEWS CORPUS...',
  '> Checking line 422 vs News Source A...',
  '> Checking line 891 vs News Source B...',
  '> MATCH FAILURE — margin_guidance: 20% != 5%',
  '> MATCH FAILURE — exec_confidence vs insider_sales',
  '> RUNNING GEMINI TRUTH-CHECK...',
  '> VERDICT COMPUTED.',
]

const NEWS_ITEMS = [
  { src: 'ET MARKETS', score: -0.82, headline: 'Margin guidance cut to 5%' },
  { src: 'BLOOMBERG',  score: -0.71, headline: 'Exec share sales raise flags' },
  { src: 'REUTERS',    score: -0.65, headline: 'Analysts downgrade to SELL' },
]

export function ContradictionEngine({ ticker }: { ticker?: string }) {
  const [filing, setFiling]       = useState(DEMO_FILING)
  const [news, setNews]           = useState(DEMO_NEWS)
  const [result, setResult]       = useState<ContradictionResult | null>(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const [termLines, setTermLines] = useState<string[]>([])
  const [showStamp, setShowStamp] = useState(false)
  const termRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!loading) return
    setTermLines([])
    setShowStamp(false)
    let i = 0
    const id = setInterval(() => {
      if (i < TERMINAL_LINES.length) {
        setTermLines(prev => [...prev, TERMINAL_LINES[i]])
        i++
      } else {
        clearInterval(id)
      }
    }, 320)
    return () => clearInterval(id)
  }, [loading])

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [termLines])

  const run = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await api.contradict(filing, news, ticker ?? '')
      setResult(r)
      if (r.contradiction_level === 'high' || r.contradiction_level === 'critical') {
        setTimeout(() => setShowStamp(true), 400)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const cfg = result ? LEVEL_CFG[result.contradiction_level] : null
  const isCritical = result?.contradiction_level === 'high' || result?.contradiction_level === 'critical'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        padding: '10px 16px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', borderBottom: '1px solid #2B2F36', background: '#131720',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Cpu size={13} color="#E31B23" />
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, letterSpacing: '0.1em', color: '#E8EAF0', textTransform: 'uppercase' }}>
            Contradiction Engine
          </span>
          {ticker && (
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, padding: '1px 6px', border: '1px solid #2B2F36', color: '#5A6070' }}>
              {ticker}
            </span>
          )}
        </div>
        <button onClick={run} disabled={loading} style={{
          background: loading ? '#2B2F36' : '#E31B23', color: '#fff', border: 'none',
          padding: '6px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
          fontWeight: 700, letterSpacing: '0.1em', cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.7 : 1,
        }}>
          {loading ? '◈ SCANNING...' : '▶ RUN AUDIT'}
        </button>
      </div>

      {/* Three columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', flex: 1, minHeight: 0 }}>

        {/* COL 1 — Filing */}
        <div id="panel-filing" style={{
          borderRight: '1px solid #2B2F36',
          display: 'flex', flexDirection: 'column',
          outline: loading ? '1px solid #E31B23' : 'none',
          boxShadow: loading ? '0 0 8px rgba(227,27,35,0.2)' : 'none',
          transition: 'outline 0.3s, box-shadow 0.3s',
        }}>
          <ColHeader icon={<FileText size={12} />} label="COL I — THE LEGAL" sub="Annual Report · SEC/SEBI Filing" accent="#5A6070" />
          <div style={{ flex: 1, padding: 16 }}>
            <div style={{
              background: '#FAFAF7', border: '1px solid #D4D0C8', padding: 12,
              height: '100%', position: 'relative',
              backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 23px, rgba(0,0,0,0.04) 23px, rgba(0,0,0,0.04) 24px)',
            }}>
              <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#888', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 8 }}>
                § Management Disclosure — FY2024
              </div>
              <textarea value={filing} onChange={e => setFiling(e.target.value)}
                style={{
                  width: '100%', background: 'transparent', border: 'none', outline: 'none',
                  resize: 'none', fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
                  lineHeight: 1.8, color: '#1A1A1A', height: 'calc(100% - 28px)',
                }} />
            </div>
          </div>
        </div>

        {/* COL 2 — News */}
        <div id="panel-news" style={{
          borderRight: '1px solid #2B2F36',
          display: 'flex', flexDirection: 'column',
          outline: loading ? '1px solid #E31B23' : 'none',
          boxShadow: loading ? '0 0 8px rgba(227,27,35,0.2)' : 'none',
          transition: 'outline 0.3s, box-shadow 0.3s',
        }}>
          <ColHeader icon={<Rss size={12} />} label="COL II — THE PULSE" sub="ET Markets · Live Sentiment Feed" accent="#5A6070" />
          <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {NEWS_ITEMS.map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: 8, border: '1px solid #2B2F36', background: '#0B0E11' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#5A6070', marginBottom: 2 }}>{item.src}</div>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#E8EAF0' }}>{item.headline}</div>
                </div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 700, color: item.score < -0.5 ? '#E31B23' : '#F59E0B', flexShrink: 0 }}>
                  {item.score.toFixed(2)}
                </div>
              </div>
            ))}
            <textarea value={news} onChange={e => setNews(e.target.value)} rows={5}
              style={{
                width: '100%', border: '1px solid #2B2F36', background: '#0B0E11',
                color: '#E8EAF0', fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
                lineHeight: 1.7, padding: 8, outline: 'none', resize: 'none',
              }} />
          </div>
        </div>

        {/* COL 3 — Verdict */}
        <div id="panel-verdict" style={{ display: 'flex', flexDirection: 'column', position: 'relative' }}>
          <ColHeader icon={<AlertTriangle size={12} />} label="COL III — THE ENGINE" sub="Gemini Truth-Check · Discrepancy Report" accent="#E31B23" />

          {/* Verdict stamp */}
          {showStamp && isCritical && (
            <div style={{
              position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
              justifyContent: 'center', pointerEvents: 'none', zIndex: 10,
            }}>
              <div style={{
                transform: 'rotate(-15deg)',
                border: '3px solid #E31B23', color: '#E31B23',
                fontFamily: 'JetBrains Mono, monospace', fontSize: 14, fontWeight: 700,
                letterSpacing: '0.15em', opacity: 0.85, background: 'rgba(11,14,17,0.7)',
                padding: '12px 24px', textAlign: 'center',
                boxShadow: '0 0 24px rgba(227,27,35,0.4)',
                animation: 'stamp-in 0.4s cubic-bezier(0.175,0.885,0.32,1.275) forwards',
              }}>
                CONFIRMED<br />DISCREPANCY
              </div>
            </div>
          )}

          <div ref={termRef} style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
            {/* Terminal */}
            <div style={{
              padding: 12, background: '#0B0E11', border: '1px solid #2B2F36',
              minHeight: 120, maxHeight: 160, overflowY: 'auto',
              fontFamily: 'JetBrains Mono, monospace', fontSize: 10, lineHeight: 1.6, color: '#5A6070',
            }}>
              {termLines.length === 0 && !result && (
                <span style={{ color: '#3A3F4A' }}>{'>'} AWAITING INPUT. PRESS RUN AUDIT.</span>
              )}
              {termLines.map((line, i) => (
                <div key={i} style={{
                  color: line.includes('FAILURE') ? '#E31B23' : line.includes('VERDICT') ? '#00C805' : '#5A6070',
                }}>
                  {line}
                </div>
              ))}
              {loading && <span style={{ color: '#00C805' }}>█</span>}
            </div>

            {error && (
              <div style={{ padding: 8, border: '1px solid #E31B23', color: '#E31B23', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>
                ERROR: {error}
              </div>
            )}

            {result && cfg && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Badge */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                  background: isCritical ? '#3D0A0C' : '#002B01', border: `1px solid ${cfg.color}`,
                }}>
                  {isCritical
                    ? <AlertTriangle size={13} color={cfg.color} />
                    : <CheckCircle  size={13} color={cfg.color} />}
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: cfg.color }}>
                    {cfg.label}
                  </span>
                </div>

                {/* Gauge */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#5A6070', marginBottom: 4 }}>
                    <span>CONTRADICTION GAUGE</span>
                    <span style={{ color: cfg.color }}>{cfg.pct}%</span>
                  </div>
                  <div style={{ height: 4, background: '#2B2F36' }}>
                    <div style={{ height: 4, width: `${cfg.pct}%`, background: cfg.color, transition: 'width 0.7s' }} />
                  </div>
                </div>

                {/* Contradictions */}
                {result.contradictions.map((c, i) => (
                  <div key={i} style={{
                    display: 'flex', gap: 8, padding: 8,
                    border: '1px solid #2B2F36', borderLeft: `2px solid ${cfg.color}`,
                    fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#E8EAF0',
                  }}>
                    <span style={{ color: cfg.color, flexShrink: 0 }}>▸</span>
                    {c}
                  </div>
                ))}

                {/* Risk summary */}
                <div style={{
                  padding: 8, border: '1px solid #2B2F36', background: '#0B0E11',
                  fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#5A6070', lineHeight: 1.7,
                }}>
                  <span style={{ display: 'block', fontSize: 9, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#3A3F4A', marginBottom: 4 }}>
                    Risk Assessment
                  </span>
                  {result.risk_summary}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function ColHeader({ icon, label, sub, accent }: {
  icon: React.ReactNode; label: string; sub: string; accent: string
}) {
  return (
    <div style={{
      padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8,
      borderBottom: '1px solid #2B2F36', background: '#131720',
    }}>
      <span style={{ color: accent }}>{icon}</span>
      <div>
        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#E8EAF0' }}>
          {label}
        </div>
        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#5A6070' }}>
          {sub}
        </div>
      </div>
    </div>
  )
}
