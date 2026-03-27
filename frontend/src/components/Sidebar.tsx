import { Zap, BarChart2, Clock, ChevronRight, Target } from 'lucide-react'
import type { Signal } from '../types'

type View = 'zenith' | 'contradiction' | 'analysis'

interface HistoryItem {
  ticker: string
  signal: Signal
  score: number
  time: string
}

interface Props {
  activeView: View
  onView: (v: View) => void
  history: HistoryItem[]
  onHistoryClick: (ticker: string) => void
}

const SIGNAL_COLOR: Record<Signal, string> = {
  STRONG_BUY:  '#00C805',
  BUY:         '#00C805',
  NEUTRAL:     '#F59E0B',
  SELL:        '#E31B23',
  STRONG_SELL: '#E31B23',
}

const NAV = [
  { id: 'zenith'        as View, label: 'Zenith Dashboard',    icon: Target   },
  { id: 'contradiction' as View, label: 'Contradiction Engine', icon: Zap      },
  { id: 'analysis'      as View, label: 'Alpha Analysis',       icon: BarChart2 },
]

export function Sidebar({ activeView, onView, history, onHistoryClick }: Props) {
  return (
    <aside
      className="flex flex-col h-full"
      style={{
        width: 200,
        borderRight: '1px solid #2B2F36',
        background: '#131720',
        flexShrink: 0,
      }}
    >
      {/* Navigation */}
      <div style={{ borderBottom: '1px solid #2B2F36' }}>
        <div
          className="px-3 py-2 text-[9px] tracking-widest uppercase"
          style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}
        >
          Navigation
        </div>
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onView(id)}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left"
            style={{
              background: activeView === id ? '#1A1F2E' : 'transparent',
              color: activeView === id ? '#E8EAF0' : '#5A6070',
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: '11px',
              cursor: 'pointer',
              border: 'none',
              borderLeft: activeView === id ? '2px solid #E31B23' : '2px solid transparent',
            }}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {/* Audit history */}
      <div className="flex-1 overflow-y-auto">
        <div
          className="px-3 py-2 flex items-center gap-1.5 text-[9px] tracking-widest uppercase sticky top-0"
          style={{
            color: '#5A6070',
            fontFamily: 'JetBrains Mono, monospace',
            background: '#131720',
            borderBottom: '1px solid #2B2F36',
          }}
        >
          <Clock size={9} />
          Audit History
        </div>

        {history.length === 0 && (
          <div
            className="px-3 py-4 text-[10px]"
            style={{ color: '#3A3F4A', fontFamily: 'JetBrains Mono, monospace' }}
          >
            No audits yet.
            <br />Run your first analysis.
          </div>
        )}

        {history.map((item, i) => (
          <button
            key={i}
            onClick={() => onHistoryClick(item.ticker)}
            className="w-full px-3 py-2.5 text-left flex items-center justify-between group"
            style={{
              background: 'transparent',
              cursor: 'pointer',
              border: 'none',
              borderBottom: '1px solid #1A1F2E',
            }}
          >
            <div>
              <div
                className="text-xs font-semibold"
                style={{ color: '#E8EAF0', fontFamily: 'JetBrains Mono, monospace' }}
              >
                {item.ticker}
              </div>
              <div
                className="text-[9px] mt-0.5"
                style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}
              >
                {item.time}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="text-[9px] font-bold"
                style={{ color: SIGNAL_COLOR[item.signal], fontFamily: 'JetBrains Mono, monospace' }}
              >
                {Math.round(item.score * 100)}
              </span>
              <ChevronRight size={10} style={{ color: '#3A3F4A' }} />
            </div>
          </button>
        ))}
      </div>

      {/* Status footer */}
      <div
        className="px-3 py-2"
        style={{ borderTop: '1px solid #2B2F36' }}
      >
        {[
          ['Gemini 1.5', '#00C805'],
          ['pgvector',   '#00C805'],
          ['Supabase',   '#00C805'],
        ].map(([label, color]) => (
          <div key={label} className="flex items-center justify-between py-0.5">
            <span
              className="text-[9px]"
              style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}
            >
              {label}
            </span>
            <span className="text-[9px]" style={{ color }}>●</span>
          </div>
        ))}
      </div>
    </aside>
  )
}
