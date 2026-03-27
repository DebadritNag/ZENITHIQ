/**
 * SentimentDivergencePanel
 * ------------------------
 * Shows retail vs. insider sentiment and the divergence signal.
 */

import type { SentimentDivergence } from '../types'

interface Props {
  data: SentimentDivergence
}

const SIGNAL_CFG = {
  'ALIGNED':           { color: '#00C805', bg: '#002B01' },
  'DIVERGING':         { color: '#F59E0B', bg: '#2D1F00' },
  'MANIPULATION RISK': { color: '#E31B23', bg: '#3D0A0C' },
}

function ScoreBar({ value, label }: { value: number; label: string }) {
  // value is -1 to +1; map to 0–100% for display
  const pct = Math.round(((value + 1) / 2) * 100)
  const color = value > 0.15 ? '#00C805' : value < -0.15 ? '#E31B23' : '#F59E0B'

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color: '#5A6070' }}>{label}</span>
        <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color, fontWeight: 700 }}>
          {value > 0 ? '+' : ''}{value.toFixed(2)}
        </span>
      </div>
      {/* Centred bar: left half = bearish, right half = bullish */}
      <div style={{ height: 4, background: '#2B2F36', position: 'relative' }}>
        <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: '#3A3F4A' }} />
        {value >= 0 ? (
          <div style={{ position: 'absolute', left: '50%', top: 0, height: 4, width: `${pct - 50}%`, background: color, transition: 'width 0.7s' }} />
        ) : (
          <div style={{ position: 'absolute', right: '50%', top: 0, height: 4, width: `${50 - pct}%`, background: color, transition: 'width 0.7s' }} />
        )}
      </div>
    </div>
  )
}

export function SentimentDivergencePanel({ data }: Props) {
  const cfg = SIGNAL_CFG[data.signal] ?? SIGNAL_CFG['DIVERGING']
  const divergence = Math.abs(data.retail_sentiment - data.insider_activity)

  return (
    <div style={{ border: '1px solid #2B2F36', background: '#131720', padding: 20 }}>
      <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, letterSpacing: '0.15em', color: '#5A6070', textTransform: 'uppercase', marginBottom: 12 }}>
        Sentiment Divergence · Hype vs. Insiders
      </div>

      <ScoreBar value={data.retail_sentiment} label="RETAIL SENTIMENT" />
      <ScoreBar value={data.insider_activity} label="INSIDER ACTIVITY" />

      {/* Divergence gauge */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color: '#5A6070' }}>DIVERGENCE GAP</span>
          <span style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color: cfg.color, fontWeight: 700 }}>
            {(divergence * 100).toFixed(0)}%
          </span>
        </div>
        <div style={{ height: 4, background: '#2B2F36' }}>
          <div style={{ height: 4, width: `${Math.min(100, divergence * 100)}%`, background: cfg.color, transition: 'width 0.7s' }} />
        </div>
      </div>

      {/* Signal badge */}
      <div style={{
        display: 'inline-block', padding: '4px 10px',
        border: `1px solid ${cfg.color}`, background: cfg.bg,
        fontFamily: 'JetBrains Mono,monospace', fontSize: 11, fontWeight: 700,
        letterSpacing: '0.08em', color: cfg.color,
      }}>
        {data.signal}
      </div>
    </div>
  )
}
