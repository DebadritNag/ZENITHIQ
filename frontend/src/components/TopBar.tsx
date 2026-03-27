import { useState } from 'react'
import { Search, HelpCircle, Activity } from 'lucide-react'
import logoSrc from '../assets/logo.png'

const TICKER_ITEMS = [
  { sym: 'RELIANCE.NS', price: '2,847.30', chg: '+1.2%', up: true },
  { sym: 'TCS.NS',      price: '3,921.15', chg: '-0.4%', up: false },
  { sym: 'INFY.NS',     price: '1,456.80', chg: '+0.8%', up: true },
  { sym: 'HDFCBANK.NS', price: '1,623.45', chg: '-0.2%', up: false },
  { sym: 'WIPRO.NS',    price: '487.60',   chg: '+2.1%', up: true },
  { sym: 'AAPL',        price: '189.42',   chg: '+0.6%', up: true },
  { sym: 'TSLA',        price: '248.73',   chg: '-1.8%', up: false },
  { sym: 'MSFT',        price: '415.20',   chg: '+0.3%', up: true },
  { sym: 'NVDA',        price: '875.40',   chg: '+3.2%', up: true },
  { sym: 'HYPE_INDEX',  price: '72.4',     chg: 'HIGH',  up: false },
]

interface Props {
  onAnalyse: (ticker: string) => void
  loading: boolean
  onShowTour: () => void
}

export function TopBar({ onAnalyse, loading, onShowTour }: Props) {
  const [input, setInput] = useState('')

  const submit = () => {
    const t = input.trim().toUpperCase()
    if (t) { onAnalyse(t); setInput('') }
  }

  return (
    <div style={{ borderBottom: '1px solid #2B2F36' }}>
      {/* Scrolling ticker */}
      <div
        className="overflow-hidden py-1"
        style={{ background: '#0B0E11', borderBottom: '1px solid #2B2F36' }}
      >
        <div className="ticker-track inline-flex gap-0 whitespace-nowrap">
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-2 px-4 text-[10px]"
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                borderRight: '1px solid #2B2F36',
                color: item.up ? '#00C805' : '#E31B23',
              }}
            >
              <Activity size={8} />
              <span style={{ color: '#5A6070' }}>{item.sym}</span>
              <span>{item.price}</span>
              <span>{item.chg}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Main header bar */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ background: '#131720' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 shrink-0">
          <img
            src={logoSrc}
            alt="Zenith IQ"
            style={{
              height: 44,
              width: 'auto',
              objectFit: 'contain',
              display: 'block',
              transition: 'transform 0.2s ease, filter 0.2s ease',
              filter: 'brightness(1)',
            }}
            onMouseEnter={e => {
              const el = e.currentTarget
              el.style.transform = 'scale(1.06)'
              el.style.filter = 'brightness(1.15) drop-shadow(0 0 6px rgba(0,200,5,0.35))'
            }}
            onMouseLeave={e => {
              const el = e.currentTarget
              el.style.transform = 'scale(1)'
              el.style.filter = 'brightness(1)'
            }}
          />
          <div>
            <div
              className="text-sm font-bold tracking-widest"
              style={{ fontFamily: 'Playfair Display, serif', color: '#E8EAF0' }}
            >
              ZENITH IQ
            </div>
            <div
              className="text-[9px] tracking-widest"
              style={{ color: '#5A6070', fontFamily: 'JetBrains Mono, monospace' }}
            >
              FINANCIAL INTELLIGENCE TERMINAL
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="flex items-center gap-0 flex-1 max-w-md mx-8">
          <div
            className="flex items-center gap-2 px-3 py-2 flex-1"
            style={{ border: '1px solid #2B2F36', borderRight: 'none', background: '#0B0E11' }}
          >
            <Search size={12} style={{ color: '#5A6070' }} />
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submit()}
              placeholder="TICKER / COMPANY NAME..."
              className="flex-1 bg-transparent outline-none text-xs"
              style={{
                color: '#E8EAF0',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            />
          </div>
          <button
            onClick={submit}
            disabled={loading}
            className="px-4 py-2 text-xs font-bold tracking-widest disabled:opacity-40"
            style={{
              background: loading ? '#2B2F36' : '#E31B23',
              color: '#fff',
              border: '1px solid #E31B23',
              fontFamily: 'JetBrains Mono, monospace',
              cursor: loading ? 'not-allowed' : 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {loading ? '◈ RUNNING' : '▶ AUDIT'}
          </button>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-3">
          <div
            className="text-[10px] px-2 py-1"
            style={{
              border: '1px solid #00C805',
              color: '#00C805',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            ● LIVE
          </div>
          <button
            onClick={onShowTour}
            className="flex items-center gap-1.5 text-[10px] px-2 py-1"
            style={{
              border: '1px solid #2B2F36',
              color: '#5A6070',
              background: 'transparent',
              fontFamily: 'JetBrains Mono, monospace',
              cursor: 'pointer',
            }}
          >
            <HelpCircle size={11} />
            TOUR
          </button>
        </div>
      </div>
    </div>
  )
}
