/**
 * QuantInsightPanel
 * -----------------
 * Displays detected technical pattern, backtest success rate, and confidence.
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { QuantInsight } from '../types'

interface Props {
  data: QuantInsight
}

const PATTERN_LABELS: Record<string, { label: string; bullish: boolean | null }> = {
  'breakout_bullish':           { label: 'Bullish Breakout',          bullish: true  },
  'breakout_bearish':           { label: 'Bearish Breakout',          bullish: false },
  'head_and_shoulders':         { label: 'Head & Shoulders',          bullish: false },
  'inverse_head_and_shoulders': { label: 'Inverse H&S',               bullish: true  },
  'none':                       { label: 'No Pattern Detected',       bullish: null  },
}

export function QuantInsightPanel({ data }: Props) {
  const meta    = PATTERN_LABELS[data.pattern] ?? { label: data.pattern, bullish: null }
  const color   = meta.bullish === true ? '#00C805' : meta.bullish === false ? '#E31B23' : '#5A6070'
  const bg      = meta.bullish === true ? '#002B01' : meta.bullish === false ? '#3D0A0C' : '#1A1F2E'
  const Icon    = meta.bullish === true ? TrendingUp : meta.bullish === false ? TrendingDown : Minus
  const confPct = Math.round(data.confidence * 100)

  return (
    <div style={{ border: '1px solid #2B2F36', background: '#131720', padding: 20 }}>
      <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, letterSpacing: '0.15em', color: '#5A6070', textTransform: 'uppercase', marginBottom: 12 }}>
        Quant Insight · Pattern Detection
      </div>

      {/* Pattern badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '5px 10px', marginBottom: 16,
        border: `1px solid ${color}`, background: bg,
      }}>
        <Icon size={12} color={color} />
        <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 11, fontWeight: 700, color }}>
          {meta.label}
        </span>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Stat label="BACKTEST WIN RATE" value={`${data.success_rate}%`} color={data.success_rate >= 55 ? '#00C805' : '#E31B23'} />
        <Stat label="CONFIDENCE" value={`${confPct}%`} color={color} />
      </div>

      {/* Confidence bar */}
      {data.confidence > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color: '#5A6070', marginBottom: 3 }}>
            SIGNAL CONFIDENCE
          </div>
          <div style={{ height: 3, background: '#2B2F36' }}>
            <div style={{ height: 3, width: `${confPct}%`, background: color, transition: 'width 0.7s' }} />
          </div>
        </div>
      )}

      {data.pattern === 'none' && (
        <div style={{ marginTop: 8, fontFamily: 'JetBrains Mono,monospace', fontSize: 10, color: '#3A3F4A' }}>
          No significant pattern in the current price window.
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ padding: '8px 10px', border: '1px solid #2B2F36', background: '#0B0E11' }}>
      <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color: '#5A6070', marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 18, fontWeight: 700, color }}>{value}</div>
    </div>
  )
}
