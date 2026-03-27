import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { AnalysisReport, Signal } from '../types'

const SIG: Record<Signal, { color: string; bg: string; label: string; Icon: React.ElementType }> = {
  STRONG_BUY:  { color: '#00C805', bg: '#002B01', label: 'STRONG BUY',  Icon: TrendingUp   },
  BUY:         { color: '#00C805', bg: '#002B01', label: 'BUY',         Icon: TrendingUp   },
  NEUTRAL:     { color: '#F59E0B', bg: '#2D1F00', label: 'NEUTRAL',     Icon: Minus        },
  SELL:        { color: '#E31B23', bg: '#3D0A0C', label: 'SELL',        Icon: TrendingDown },
  STRONG_SELL: { color: '#E31B23', bg: '#3D0A0C', label: 'STRONG SELL', Icon: TrendingDown },
}

export function AlphaScoreCard({ report }: { report: AnalysisReport }) {
  const sig = SIG[report.signal]
  const pct = Math.round(report.alpha_score * 100)

  return (
    <div style={{ border: '1px solid #2B2F36', background: '#131720' }}>
      {/* Header */}
      <div className="px-5 py-3 flex items-center justify-between"
        style={{ borderBottom: '1px solid #2B2F36', background: '#0B0E11' }}>
        <div className="flex items-center gap-3">
          <div>
            <span className="text-lg font-bold"
              style={{ fontFamily: 'Playfair Display, serif', color: '#E8EAF0' }}>
              AUDIT: {report.ticker}
            </span>
            <span className="ml-3 text-xs" style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
              {report.company_name}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5"
          style={{ background: sig.bg, border: `1px solid ${sig.color}` }}>
          <sig.Icon size={13} style={{ color: sig.color }} />
          <span className="text-xs font-bold tracking-widest"
            style={{ color: sig.color, fontFamily: 'JetBrains Mono, monospace' }}>
            {sig.label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3" style={{ borderBottom: '1px solid #2B2F36' }}>
        {/* Score */}
        <div id="tour-alpha-score" className="p-5" style={{ borderRight: '1px solid #2B2F36' }}>
          <div className="text-[9px] tracking-widest uppercase mb-2"
            style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
            Alpha Score
          </div>
          <div className="text-6xl font-bold leading-none"
            style={{ color: sig.color, fontFamily: 'JetBrains Mono, monospace' }}>
            {pct}
          </div>
          <div className="text-xs mt-1" style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
            / 100
          </div>
          <div className="mt-3 h-1 w-full" style={{ background: '#2B2F36' }}>
            <div className="h-1 transition-all duration-700"
              style={{ width: `${pct}%`, background: sig.color }} />
          </div>
          <div className="mt-3 text-[9px]"
            style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
            {report.duration_ms}ms · {Object.keys(report.agent_results).length} agents
          </div>
        </div>

        {/* Agent bars */}
        <div id="tour-agent-breakdown" className="p-5" style={{ borderRight: '1px solid #2B2F36' }}>
          <div className="text-[9px] tracking-widest uppercase mb-3"
            style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
            Agent Breakdown
          </div>
          <div className="space-y-2.5">
            {Object.entries(report.agent_results).map(([name, res]) => {
              const s = res.score ?? 0.5
              const p = Math.round(s * 100)
              const c = s >= 0.6 ? '#00C805' : s >= 0.45 ? '#F59E0B' : '#E31B23'
              return (
                <div key={name} className="flex items-center gap-2">
                  <span className="w-16 text-[9px] shrink-0"
                    style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
                    {name.replace('Agent', '')}
                  </span>
                  <div className="flex-1 h-px" style={{ background: '#2B2F36' }}>
                    <div style={{ width: `${p}%`, background: c, height: '100%' }} />
                  </div>
                  <span className="text-[9px] w-6 text-right"
                    style={{ color: c, fontFamily: 'JetBrains Mono, monospace' }}>
                    {p}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Key risks */}
        <div id="tour-key-risks" className="p-5">
          <div className="text-[9px] tracking-widest uppercase mb-3"
            style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
            Key Risks
          </div>
          <ul className="space-y-2">
            {report.key_risks.map((r, i) => (
              <li key={i} className="flex gap-2 text-[10px]"
                style={{ fontFamily: 'JetBrains Mono, monospace', color: '#E8EAF0' }}>
                <span style={{ color: '#E31B23', flexShrink: 0 }}>▸</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Summary */}
      <div id="tour-ai-summary" className="px-5 py-4">
        <div className="text-[9px] tracking-widest uppercase mb-2"
          style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}>
          AI Summary
        </div>
        <p className="text-xs leading-relaxed"
          style={{ fontFamily: 'JetBrains Mono, monospace', color: '#E8EAF0' }}>
          {report.summary}
        </p>
      </div>
    </div>
  )
}
