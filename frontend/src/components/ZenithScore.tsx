/**
 * ZenithScore
 * -----------
 * Displays the composite Zenith Score (0–100) and signal label.
 */

interface Props {
  score:  number   // 0–100
  signal: string   // 'STRONG BUY' | 'BUY' | 'NEUTRAL' | 'SELL' | 'STRONG SELL'
  symbol: string
}

const SIGNAL_COLOR: Record<string, string> = {
  'STRONG BUY':  '#00C805',
  'BUY':         '#00C805',
  'NEUTRAL':     '#F59E0B',
  'SELL':        '#E31B23',
  'STRONG SELL': '#E31B23',
}

export function ZenithScore({ score, signal, symbol }: Props) {
  const color = SIGNAL_COLOR[signal] ?? '#F59E0B'
  const clamped = Math.max(0, Math.min(100, score))

  // Arc path for the gauge (semicircle)
  const r = 54
  const cx = 70
  const cy = 70
  const startAngle = Math.PI
  const endAngle   = startAngle + (clamped / 100) * Math.PI
  const x1 = cx + r * Math.cos(startAngle)
  const y1 = cy + r * Math.sin(startAngle)
  const x2 = cx + r * Math.cos(endAngle)
  const y2 = cy + r * Math.sin(endAngle)
  const largeArc = clamped > 50 ? 1 : 0

  return (
    <div style={{ border: '1px solid #2B2F36', background: '#131720', padding: 20 }}>
      <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, letterSpacing: '0.15em', color: '#5A6070', textTransform: 'uppercase', marginBottom: 12 }}>
        Zenith Score · {symbol}
      </div>

      {/* Gauge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <svg width={140} height={80} viewBox="0 0 140 80">
          {/* Track */}
          <path
            d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
            fill="none" stroke="#2B2F36" strokeWidth={8} strokeLinecap="round"
          />
          {/* Fill */}
          {clamped > 0 && (
            <path
              d={`M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`}
              fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
              style={{ transition: 'all 0.8s ease' }}
            />
          )}
          {/* Score text */}
          <text x={cx} y={cy - 4} textAnchor="middle"
            style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 22, fontWeight: 700, fill: color }}>
            {clamped}
          </text>
          <text x={cx} y={cy + 12} textAnchor="middle"
            style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, fill: '#5A6070' }}>
            / 100
          </text>
        </svg>

        <div>
          {/* Signal badge */}
          <div style={{
            display: 'inline-block', padding: '4px 10px', marginBottom: 8,
            border: `1px solid ${color}`, background: color === '#00C805' ? '#002B01' : color === '#E31B23' ? '#3D0A0C' : '#2D1F00',
            fontFamily: 'JetBrains Mono,monospace', fontSize: 11, fontWeight: 700,
            letterSpacing: '0.08em', color,
          }}>
            {signal}
          </div>

          {/* Score bar */}
          <div style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: 9, color: '#5A6070', marginBottom: 4 }}>
            COMPOSITE SCORE
          </div>
          <div style={{ width: 120, height: 3, background: '#2B2F36' }}>
            <div style={{ height: 3, width: `${clamped}%`, background: color, transition: 'width 0.8s' }} />
          </div>
        </div>
      </div>
    </div>
  )
}
