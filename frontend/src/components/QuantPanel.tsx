import type { AgentResult } from '../types'

interface Indicators {
  rsi: number
  rsi_signal: string
  macd_bullish: boolean
  macd_cross: boolean
  bb_position: number
  golden_cross: boolean | null
  latest_close: number
}

interface PatternData {
  pattern: string
  detected: boolean
  confidence: number
  signal: string
  key_levels: Record<string, number>
  description: string
  backtest?: {
    occurrences: number
    wins: number
    success_rate: number
    avg_return: number
    holding_bars: number
  }
}

export function QuantPanel({ result }: { result: AgentResult }) {
  if (!result.success || !result.data) return null

  const indicators = result.data.indicators as Indicators | undefined
  const patterns   = result.data.patterns as Record<string, PatternData> | undefined

  return (
    <div style={{ border: '1px solid #D1D1D1' }}>
      <div
        className="px-6 py-2"
        style={{ borderBottom: '1px solid #D1D1D1', background: '#121212' }}
      >
        <span
          className="text-xs tracking-widest uppercase text-white"
          style={{ fontFamily: 'JetBrains Mono, monospace' }}
        >
          ◈ Quant Analysis · Technical Patterns
        </span>
      </div>

      <div className="grid grid-cols-2" style={{ borderBottom: '1px solid #D1D1D1' }}>
        {/* Indicators */}
        {indicators && (
          <div className="p-6" style={{ borderRight: '1px solid #D1D1D1' }}>
            <div
              className="text-[10px] tracking-widest uppercase mb-4"
              style={{ color: '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
            >
              Technical Indicators
            </div>
            <div className="space-y-3">
              <IndicatorRow
                label="RSI (14)"
                value={`${indicators.rsi}`}
                badge={indicators.rsi_signal}
                color={
                  indicators.rsi_signal === 'oversold' ? '#006341' :
                  indicators.rsi_signal === 'overbought' ? '#E31B23' : '#B45309'
                }
              />
              <IndicatorRow
                label="MACD"
                value={indicators.macd_bullish ? 'Bullish' : 'Bearish'}
                badge={indicators.macd_cross ? 'FRESH CROSS' : undefined}
                color={indicators.macd_bullish ? '#006341' : '#E31B23'}
              />
              <IndicatorRow
                label="BB Position"
                value={`${Math.round(indicators.bb_position * 100)}%`}
                badge={
                  indicators.bb_position < 0.2 ? 'NEAR SUPPORT' :
                  indicators.bb_position > 0.8 ? 'NEAR RESISTANCE' : undefined
                }
                color={
                  indicators.bb_position < 0.2 ? '#006341' :
                  indicators.bb_position > 0.8 ? '#E31B23' : '#6B6B6B'
                }
              />
              <IndicatorRow
                label="MA Cross"
                value={
                  indicators.golden_cross === null ? 'N/A' :
                  indicators.golden_cross ? 'Golden Cross' : 'Death Cross'
                }
                color={
                  indicators.golden_cross === null ? '#6B6B6B' :
                  indicators.golden_cross ? '#006341' : '#E31B23'
                }
              />
              <IndicatorRow
                label="Last Close"
                value={`$${indicators.latest_close}`}
                color="#121212"
              />
            </div>
          </div>
        )}

        {/* Patterns */}
        {patterns && (
          <div className="p-6">
            <div
              className="text-[10px] tracking-widest uppercase mb-4"
              style={{ color: '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
            >
              Pattern Detection
            </div>
            <div className="space-y-4">
              {Object.entries(patterns).map(([key, p]) => (
                <PatternCard key={key} name={key} data={p} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function IndicatorRow({
  label, value, badge, color,
}: { label: string; value: string; badge?: string; color: string }) {
  return (
    <div className="flex items-center justify-between">
      <span
        className="text-xs"
        style={{ color: '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
      >
        {label}
      </span>
      <div className="flex items-center gap-2">
        {badge && (
          <span
            className="text-[9px] px-1.5 py-0.5"
            style={{
              border: `1px solid ${color}`,
              color,
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            {badge}
          </span>
        )}
        <span
          className="text-xs font-semibold"
          style={{ color, fontFamily: 'JetBrains Mono, monospace' }}
        >
          {value}
        </span>
      </div>
    </div>
  )
}

function PatternCard({ name, data }: { name: string; data: PatternData }) {
  const color = data.detected
    ? data.signal === 'bullish' ? '#006341' : '#E31B23'
    : '#6B6B6B'

  return (
    <div
      className="p-3"
      style={{
        border: `1px solid ${data.detected ? color : '#D1D1D1'}`,
        borderLeft: `3px solid ${color}`,
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span
          className="text-xs font-semibold"
          style={{ fontFamily: 'JetBrains Mono, monospace' }}
        >
          {name.replace(/_/g, ' ').toUpperCase()}
        </span>
        <span
          className="text-[10px] px-1.5 py-0.5"
          style={{
            background: data.detected ? color : '#D1D1D1',
            color: data.detected ? '#fff' : '#6B6B6B',
            fontFamily: 'JetBrains Mono, monospace',
          }}
        >
          {data.detected ? `${data.signal.toUpperCase()} · ${Math.round(data.confidence * 100)}%` : 'NOT DETECTED'}
        </span>
      </div>

      {data.detected && data.backtest && (
        <div
          className="grid grid-cols-3 gap-2 mt-2 pt-2"
          style={{ borderTop: '1px solid #D1D1D1' }}
        >
          {[
            ['Occurrences', data.backtest.occurrences],
            ['Win Rate',    `${Math.round(data.backtest.success_rate * 100)}%`],
            ['Avg Return',  `${(data.backtest.avg_return * 100).toFixed(1)}%`],
          ].map(([k, v]) => (
            <div key={k as string}>
              <div
                className="text-[9px]"
                style={{ color: '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
              >
                {k}
              </div>
              <div
                className="text-xs font-semibold"
                style={{ fontFamily: 'JetBrains Mono, monospace' }}
              >
                {v}
              </div>
            </div>
          ))}
        </div>
      )}

      {data.description && (
        <div
          className="text-[10px] mt-2"
          style={{ color: '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
        >
          {data.description.slice(0, 100)}
        </div>
      )}
    </div>
  )
}
